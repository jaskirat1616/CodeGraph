// View modes: files (lightweight), full (+Class+Module), complete (+Function+Method, all CALLS/IMPORTS)
var urlParams = new URLSearchParams(window.location.search);
var viewParam = urlParams.get('view');
var view = ['files', 'full', 'complete'].includes(viewParam) ? viewParam : 'files';
var animateReveal = urlParams.get('animate') !== 'false';  // Gource-like reveal; ?animate=false to disable
var cy;

function updateStats() {
  if (!cy) return;
  var nodes = cy.nodes().length;
  var edges = cy.edges().length;
  document.getElementById('stats').textContent = nodes + ' nodes, ' + edges + ' edges';
}

function showDetails(node) {
  var panel = document.getElementById('detailsPanel');
  var content = document.getElementById('detailsContent');
  if (!node) {
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');
  var data = node.data();
  var html = '<div class="detail-row"><span class="detail-label">Type</span><div class="detail-value">' + (data.label || '') + '</div></div>';
  html += '<div class="detail-row"><span class="detail-label">Name</span><div class="detail-value">' + (data.name || '(unnamed)') + '</div></div>';
  if (data.path) html += '<div class="detail-row"><span class="detail-label">Path</span><div class="detail-value">' + escapeHtml(data.path) + '</div></div>';
  var out = node.outgoers('node').length;
  var in_ = node.incomers('node').length;
  html += '<div class="detail-row"><span class="detail-label">Outgoing</span><div class="detail-value">' + out + ' connections</div></div>';
  html += '<div class="detail-row"><span class="detail-label">Incoming</span><div class="detail-value">' + in_ + ' connections</div></div>';
  if (data.expanded) html += '<div class="detail-row"><span class="detail-label">Status</span><div class="detail-value">Expanded</div></div>';
  html += '<div id="detailCode" class="detail-code" style="margin-top:0.75em;display:none;"></div>';
  content.innerHTML = html;
  var codeEl = document.getElementById('detailCode');
  var label = data.label || '';
  if (['File', 'Class', 'Function', 'Method'].indexOf(label) >= 0) {
    codeEl.style.display = 'block';
    codeEl.innerHTML = '<div class="detail-label">Code</div><pre class="code-snippet"><code>Loading…</code></pre>';
    fetch('/graph/node/' + node.id() + '/code').then(function(res) { return res.json(); }).then(function(r) {
      var pre = codeEl.querySelector('.code-snippet code');
      if (r.code != null) {
        pre.textContent = r.code;
      } else {
        pre.textContent = r.error || 'Code not available';
      }
    }).catch(function() {
      codeEl.querySelector('.code-snippet code').textContent = 'Failed to load code';
    });
  }
}
function escapeHtml(s) {
  var div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

var nodeLimit = view === 'complete' ? 2000 : 500;
var edgeLimit = view === 'complete' ? 5000 : 1000;
Promise.all([
  fetch('/graph/nodes?view=' + view + '&limit=' + nodeLimit).then(res => res.json()),
  fetch('/graph/edges?view=' + view + '&limit=' + edgeLimit).then(res => res.json())
]).then(([nodes, edges]) => {
  if (!nodes.length && !edges.length) {
    document.getElementById('cy').innerHTML = '<div style="color:#888;padding:2em;text-align:center;">No graph data. Index a repository first: <code>python3 codegraph/cli.py index_repo /path/to/repo</code></div>';
    return;
  }
  var nextView = view === 'files' ? 'full' : view === 'full' ? 'complete' : 'files';
  var nextLabel = view === 'files' ? 'Full view' : view === 'full' ? 'Complete view' : 'File view';
  document.getElementById('viewToggle').href = '?view=' + nextView;
  document.getElementById('viewToggle').textContent = nextLabel;
  var animateHref = new URL(window.location);
  animateHref.searchParams.set('animate', animateReveal ? 'false' : 'true');
  document.getElementById('animateToggle').href = animateHref.toString();
  document.getElementById('animateToggle').textContent = animateReveal ? 'No animation' : 'Animate';
  document.getElementById('detailsPanel').classList.add('hidden');
  var initialElements = nodes.map(function(n) {
    return animateReveal ? { data: n.data, classes: 'revealing' } : n;
  }).concat(edges);
  cy = cytoscape({
    container: document.getElementById('cy'),
    elements: initialElements,
    style: [
      {
        selector: 'node.revealing',
        style: { 'opacity': 0 }
      },
      {
        selector: 'node',
        style: {
          'label': 'data(name)',
          'color': '#fff',
          'text-valign': 'bottom',
          'text-margin-y': 5,
          'font-size': '12px',
          'background-color': function(ele) {
            const lbl = ele.data('label');
            if(lbl === 'File') return '#0074D9';
            if(lbl === 'Class') return '#FF4136';
            if(lbl === 'Function') return '#2ECC40';
            if(lbl === 'Method') return '#FFDC00';
            if(lbl === 'Repository') return '#B10DC9';
            return '#AAAAAA';
          }
        }
      },
      {
        selector: 'node.dimmed',
        style: { 'opacity': 0.15 }
      },
      {
        selector: 'edge',
        style: {
          'label': 'data(label)',
          'color': '#888',
          'font-size': '10px',
          'width': 2,
          'line-color': '#555',
          'target-arrow-color': '#555',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier'
        }
      }
    ],
    layout: {
      name: 'cose',
      padding: 50,
      nodeRepulsion: 400000,
      idealEdgeLength: 100,
      edgeElasticity: 100,
      animate: animateReveal ? 'end' : false
    }
  });
  updateStats();

  if (animateReveal && cy.nodes().length > 0) {
    cy.edges().style('opacity', 0);
    var order = { 'Repository': 0, 'File': 1, 'Class': 2, 'Module': 3, 'Function': 4, 'Method': 5 };
    var sorted = cy.nodes().sort(function(a, b) {
      var oa = order[a.data('label')] ?? 6;
      var ob = order[b.data('label')] ?? 6;
      return oa - ob;
    });
    var delayMs = Math.max(30, Math.min(150, 4000 / sorted.length));
    var batchSize = Math.max(1, Math.floor(sorted.length / 80));
    function revealNext(i) {
      if (i >= sorted.length) {
        cy.edges().animate({ style: { opacity: 0.8 } }, { duration: 300 });
        return;
      }
      var batch = sorted.slice(i, i + batchSize);
      batch.forEach(function(n) {
        n.removeClass('revealing');
        n.animate({ style: { opacity: 1 } }, { duration: 350 });
      });
      var outgoing = batch.flatMap(function(n) { return n.connectedEdges().toArray(); });
      outgoing.forEach(function(e) {
        if (e.style('opacity') === 0) e.animate({ style: { opacity: 0.8 } }, { duration: 250 });
      });
      setTimeout(function() { revealNext(i + batchSize); }, delayMs);
    }
    cy.once('layoutstop', function() { setTimeout(function() { revealNext(0); }, 200); });
  }

  cy.on('tap', 'node', function(evt){
    var node = evt.target;
    var nodeId = node.id();
    showDetails(node);
    
    // Lazy-load children when a node is clicked
    if (!node.data('expanded')) {
      fetch('/graph/expand/' + nodeId)
        .then(res => res.json())
        .then(data => {
            if (data.nodes.length > 0 || data.edges.length > 0) {
                var newNodes = data.nodes.map(function(n) { return { data: n.data, classes: animateReveal ? 'revealing' : '' }; });
                var added = cy.add([...newNodes, ...data.edges]);
                var addedNodes = added.filter('node');
                var addedEdges = added.filter('edge');
                addedEdges.style('opacity', 0);
                node.data('expanded', true);
                updateStats();
                showDetails(node);
                var layout = cy.layout({
                  name: 'cose',
                  padding: 50,
                  nodeRepulsion: 400000,
                  idealEdgeLength: 100,
                  edgeElasticity: 100,
                  animate: animateReveal
                });
                layout.run();
                if (animateReveal && addedNodes.length > 0) {
                  layout.promiseOn('layoutstop').then(function() {
                    setTimeout(function() {
                      addedNodes.forEach(function(n, i) {
                        setTimeout(function() {
                          n.removeClass('revealing');
                          n.animate({ style: { opacity: 1 } }, { duration: 300 });
                          n.connectedEdges().animate({ style: { opacity: 0.8 } }, { duration: 200 });
                        }, i * 60);
                      });
                    }, 150);
                  });
                } else {
                  addedNodes.removeClass('revealing');
                  addedEdges.style('opacity', 0.8);
                }
            }
        });
    }
  });
  cy.on('tap', function(evt) {
    if (evt.target === cy) showDetails(null);
  });
  document.getElementById('search').addEventListener('input', function() {
    var q = this.value.trim().toLowerCase();
    cy.nodes().removeClass('dimmed');
    if (!q) return;
    cy.nodes().forEach(function(n) {
      var name = (n.data('name') || '').toLowerCase();
      var path = (n.data('path') || '').toLowerCase();
      if (!name.includes(q) && !path.includes(q)) n.addClass('dimmed');
    });
  });
}).catch(function(err) {
  document.getElementById('cy').innerHTML = '<div style="color:#c33;padding:2em;text-align:center;">Failed to load graph. Ensure FalkorDB is running and a repo has been indexed.</div>';
  console.error(err);
});