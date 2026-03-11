// File-level view by default for large graphs; use ?view=full in URL for Classes+Modules too
var urlParams = new URLSearchParams(window.location.search);
var view = urlParams.get('view') === 'full' ? 'full' : 'files';
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
  if (data.path) html += '<div class="detail-row"><span class="detail-label">Path</span><div class="detail-value">' + data.path + '</div></div>';
  var out = node.outgoers('node').length;
  var in_ = node.incomers('node').length;
  html += '<div class="detail-row"><span class="detail-label">Outgoing</span><div class="detail-value">' + out + ' connections</div></div>';
  html += '<div class="detail-row"><span class="detail-label">Incoming</span><div class="detail-value">' + in_ + ' connections</div></div>';
  if (data.expanded) html += '<div class="detail-row"><span class="detail-label">Status</span><div class="detail-value">Expanded</div></div>';
  content.innerHTML = html;
}

Promise.all([
  fetch('/graph/nodes?view=' + view + '&limit=500').then(res => res.json()),
  fetch('/graph/edges?view=' + view + '&limit=1000').then(res => res.json())
]).then(([nodes, edges]) => {
  if (!nodes.length && !edges.length) {
    document.getElementById('cy').innerHTML = '<div style="color:#888;padding:2em;text-align:center;">No graph data. Index a repository first: <code>python3 codegraph/cli.py index_repo /path/to/repo</code></div>';
    return;
  }
  document.getElementById('viewToggle').href = view === 'files' ? '?view=full' : '?view=files';
  document.getElementById('viewToggle').textContent = view === 'files' ? 'Full view' : 'File view';
  document.getElementById('detailsPanel').classList.add('hidden');
  cy = cytoscape({
    container: document.getElementById('cy'),
    elements: [...nodes, ...edges],
    style: [
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
      edgeElasticity: 100
    }
  });
  updateStats();

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
                cy.add([...data.nodes, ...data.edges]);
                node.data('expanded', true);
                updateStats();
                showDetails(node);
                cy.layout({
                  name: 'cose',
                  padding: 50,
                  nodeRepulsion: 400000,
                  idealEdgeLength: 100,
                  edgeElasticity: 100
                }).run();
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