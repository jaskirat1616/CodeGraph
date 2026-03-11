(function() {
  var viewParam = (new URLSearchParams(window.location.search)).get('view');
  var view = ['files', 'full', 'complete'].includes(viewParam) ? viewParam : 'files';
  var nodeLimit = view === 'complete' ? 2000 : 500;
  var edgeLimit = view === 'complete' ? 5000 : 1000;

  window.codegraphHighlightIds = new Set();
  window.codegraphGraph = null;
  window.codegraphSearchQuery = '';

  var neonColors = {
    File: '#00d4ff',
    Class: '#ff2d6a',
    Function: '#00ff9f',
    Method: '#ffb800',
    Repository: '#bf5fff',
    Module: '#7eb8da'
  };
  function getLabelColors() {
    return neonColors;
  }
  function getDimColor() {
    return 'rgba(100,100,120,0.3)';
  }
  function getLinkColor() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'rgba(80,90,120,0.45)' : 'rgba(150,150,200,0.5)';
  }
  function getBgColor() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? '#f5f5f7' : '#0a0a12';
  }
  function getSpriteTextColor() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? '#1e293b' : '#e2e8f0';
  }
  function getHighlightColor() {
    return '#00ffaa';
  }

  function nodeColorFn(n) {
    var labelColors = getLabelColors();
    var base = labelColors[n.label] || '#88aacc';
    if (window.codegraphHighlightIds.has(String(n.id))) return getHighlightColor();
    var q = (window.codegraphSearchQuery || '').trim().toLowerCase();
    if (q) {
      var name = ((n.name || '') + ' ' + (n.path || '')).toLowerCase();
      if (!name.includes(q)) return getDimColor();
    }
    return base;
  }
  function nodeValFn(n) {
    if (window.codegraphHighlightIds.has(String(n.id))) return 120;
    var q = (window.codegraphSearchQuery || '').trim().toLowerCase();
    if (q) {
      var name = ((n.name || '') + ' ' + (n.path || '')).toLowerCase();
      return name.includes(q) ? 100 : 50;
    }
    return 100;
  }

  function updateStats(nodes, edges) {
    var el = document.getElementById('stats');
    if (el) el.textContent = (nodes || 0) + ' nodes, ' + (edges || 0) + ' edges';
  }

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  window.codegraphShowDetails = function(nodeData) {
    var panel = document.getElementById('detailsPanel');
    var content = document.getElementById('detailsContent');
    if (!nodeData) {
      panel.classList.add('hidden');
      return;
    }
    panel.classList.remove('hidden');
    var d = nodeData;
    var name = d.name || d.id || '(unnamed)';
    var path = d.path || '';
    var html = '<div class="detail-row"><span class="detail-label">Type</span><div class="detail-value">' + escapeHtml(d.label || '') + '</div></div>';
    html += '<div class="detail-row"><span class="detail-label">Name</span><div class="detail-value">' + escapeHtml(name) + '</div></div>';
    if (path) html += '<div class="detail-row"><span class="detail-label">Path</span><div class="detail-value">' + escapeHtml(path) + '</div></div>';
    html += '<div class="detail-row"><span class="detail-label">ID</span><div class="detail-value">' + escapeHtml(d.id) + '</div></div>';
    var label = d.label || '';
    if (['File', 'Class', 'Function', 'Method'].indexOf(label) >= 0) {
      html += '<div class="detail-row detail-code-row"><span class="detail-label">Code</span><div id="detailCode" class="detail-code"><pre class="code-snippet"><code>Loading…</code></pre></div></div>';
    }
    content.innerHTML = html;
    if (['File', 'Class', 'Function', 'Method'].indexOf(label) >= 0) {
      fetch('/graph/node/' + encodeURIComponent(d.id) + '/code')
        .then(function(r) { return r.json(); })
        .then(function(r) {
          var el = document.getElementById('detailCode');
          if (!el) return;
          var code = el.querySelector('.code-snippet code');
          if (code) code.textContent = r.code != null ? r.code : (r.error || 'Code not available');
        })
        .catch(function() {
          var el = document.getElementById('detailCode');
          if (el) { var c = el.querySelector('.code-snippet code'); if (c) c.textContent = 'Failed to load code'; }
        });
    }
  };

  function zoomToMatchingNodes(filterFn) {
    if (!window.codegraphGraph || typeof window.codegraphGraph.zoomToFit !== 'function') return;
    requestAnimationFrame(function() {
      requestAnimationFrame(function() {
        try {
          window.codegraphGraph.zoomToFit(600, 120, filterFn || undefined);
        } catch (e) { /* ignore */ }
      });
    });
  }

  var searchZoomTimeout;
  var searchEl = document.getElementById('search');
  if (searchEl) searchEl.addEventListener('input', function() {
    window.codegraphSearchQuery = this.value;
    if (window.codegraphGraph && typeof window.codegraphGraph.refresh === 'function') {
      window.codegraphGraph.refresh();
    }
    clearTimeout(searchZoomTimeout);
    searchZoomTimeout = setTimeout(function() {
      var q = (window.codegraphSearchQuery || '').trim().toLowerCase();
      if (!q) {
        zoomToMatchingNodes(null);
        return;
      }
      zoomToMatchingNodes(function(n) {
        var name = ((n.name || '') + ' ' + (n.path || '')).toLowerCase();
        return name.includes(q);
      });
    }, 400);
  });

  window.codegraphHighlightFromResults = function(results) {
    if (!window.codegraphGraph) return;
    window.codegraphHighlightIds.clear();
    var clearBtn = document.getElementById('clearHighlight');
    if (!results || !Array.isArray(results)) {
      if (typeof window.codegraphGraph.refresh === 'function') window.codegraphGraph.refresh();
      if (clearBtn) clearBtn.style.display = 'none';
      return;
    }
    results.forEach(function(row) {
      if (Array.isArray(row)) row.forEach(function(c) {
        if (c != null && c !== '') window.codegraphHighlightIds.add(String(c));
      });
    });
    if (typeof window.codegraphGraph.refresh === 'function') window.codegraphGraph.refresh();
    if (clearBtn) clearBtn.style.display = 'inline-block';
    if (window.codegraphHighlightIds.size > 0) {
      zoomToMatchingNodes(function(n) {
        return window.codegraphHighlightIds.has(String(n.id));
      });
    } else {
      zoomToMatchingNodes(null);
    }
  };

  window.codegraphClearHighlight = function() {
    window.codegraphHighlightIds.clear();
    var clearBtn = document.getElementById('clearHighlight');
    if (clearBtn) clearBtn.style.display = 'none';
    if (window.codegraphGraph && typeof window.codegraphGraph.refresh === 'function') {
      window.codegraphGraph.refresh();
    }
    zoomToMatchingNodes(null);
  };

  var clearBtn = document.getElementById('clearHighlight');
  if (clearBtn) clearBtn.addEventListener('click', window.codegraphClearHighlight);

  var container = document.getElementById('graph3d');
  if (!container) return;

  Promise.all([
    fetch('/graph/nodes?view=' + view + '&limit=' + nodeLimit).then(function(r) { return r.json(); }),
    fetch('/graph/edges?view=' + view + '&limit=' + edgeLimit).then(function(r) { return r.json(); })
  ]).then(function(_ref) {
    var nodes = _ref[0];
    var edges = _ref[1];
    if (!nodes.length && !edges.length) {
      var emptyColor = document.documentElement.getAttribute('data-theme') === 'light' ? '#6b7280' : '#888';
      container.innerHTML = '<div class="graph-empty">No graph data. Index a repository first: <code>python3 codegraph/cli.py index_repo /path/to/repo</code></div>';
      return;
    }

    var nodeMap = {};
    var graphNodes = nodes.map(function(n) {
      var d = n.data || n;
      var id = String(d.id);
      nodeMap[id] = { id: id, name: d.name || id, label: d.label || 'Node', path: d.path || '' };
      return { id: id, name: d.name || id, label: d.label || 'Node', path: d.path || '' };
    });
    var graphLinks = edges
      .filter(function(e) {
        var d = e.data || e;
        return nodeMap[d.source] && nodeMap[d.target];
      })
      .map(function(e) {
        var d = e.data || e;
        return { source: String(d.source), target: String(d.target) };
      });

    var Graph = window.ForceGraph3D;
    if (!Graph) {
      container.innerHTML = '<div class="graph-empty">Loading 3D graph…</div>';
      return;
    }

    var THREE = window.THREE;
    var SpriteText = window.SpriteText;
    function createNeonMetallicNode(n) {
      if (!THREE) return null;
      var color = nodeColorFn(n);
      var geom = new THREE.SphereGeometry(6, 28, 24);
      var mat = new THREE.MeshStandardMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.3,
        metalness: 0.85,
        roughness: 0.2
      });
      return new THREE.Mesh(geom, mat);
    }
    function displayName(n) {
      var s = (n.name || n.id || 'node').toString();
      var i = Math.max(s.lastIndexOf('/'), s.lastIndexOf('\\'));
      return i >= 0 ? s.slice(i + 1) : s;
    }
    function createNodeWithText(n) {
      var sphere = createNeonMetallicNode(n);
      if (!sphere || !SpriteText) return sphere;
      var label = displayName(n);
      if (label.length > 22) label = label.slice(0, 19) + '...';
      var st = new SpriteText(label, 5);
      st.color = getSpriteTextColor();
      st.textHeight = 5;
      st.fontFace = 'system-ui, -apple-system, sans-serif';
      if (st.material) st.material.depthWrite = false;
      if (st.center) st.center.y = -0.6;
      st.position.z = 2;
      st.position.y = 4;
      var group = new THREE.Group();
      group.add(sphere);
      group.add(st);
      return group;
    }

    var graph = Graph()(container)
      .graphData({ nodes: graphNodes, links: graphLinks })
      .nodeLabel(function(n) { return (n.label ? n.label + ': ' : '') + displayName(n); })
      .nodeColor(nodeColorFn)
      .nodeVal(nodeValFn)
      .nodeRelSize(180)
      .nodeOpacity(1)
      .linkColor(function() { return getLinkColor(); })
      .linkWidth(0)
      .linkOpacity(0.6)
      .nodeThreeObject(createNodeWithText)
      .onNodeClick(function(n) {
        window.codegraphShowDetails(n);
      })
      .backgroundColor(getBgColor());

    window.codegraphGraph = graph;
    updateStats(graphNodes.length, graphLinks.length);

    window.addEventListener('themechange', function() {
      graph.backgroundColor(getBgColor());
      graph.linkColor(function() { return getLinkColor(); });
      if (typeof graph.refresh === 'function') graph.refresh();
    });
  }).catch(function(err) {
    container.innerHTML = '<div class="graph-empty">Failed to load graph. Ensure FalkorDB is running.</div>';
  });

  var nextView = view === 'files' ? 'full' : view === 'full' ? 'complete' : 'files';
  var nextLabel = view === 'files' ? 'Full view' : view === 'full' ? 'Complete view' : 'File view';
  var viewEl = document.getElementById('viewToggle');
  if (viewEl) { viewEl.href = '?view=' + nextView; viewEl.textContent = nextLabel; }
})();
