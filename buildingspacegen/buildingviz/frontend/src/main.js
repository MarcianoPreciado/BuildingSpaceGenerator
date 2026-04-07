/**
 * Main entry point — initializes all modules and drives the render loop.
 */

window.App = (() => {
  const canvas = document.getElementById('main-canvas');
  const tooltip = document.getElementById('tooltip');
  const ctx = canvas.getContext('2d');

  let _scene = null;
  let _currentFreq = 900000000;

  function resize() {
    const container = canvas.parentElement;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    Interaction.fitToScene(canvas.width, canvas.height);
    redraw();
  }

  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!_scene) {
      ctx.fillStyle = '#666';
      ctx.font = '16px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Loading scene...', canvas.width / 2, canvas.height / 2);
      return;
    }

    const transform = Interaction.getTransform();
    FloorPlan.draw(ctx, transform);
    Links.draw(ctx, transform);
    Devices.draw(ctx, transform);
  }

  function loadScene(scene) {
    _scene = scene;
    FloorPlan.setScene(scene);
    Devices.setScene(scene);
    Links.setScene(scene);
    Interaction.setScene(scene);
    Interaction.fitToScene(canvas.width, canvas.height);
    Filters.syncPowerRange(scene, true);
    Filters.buildLegend(scene);
    Filters.updateStats(scene);
    redraw();
  }

  async function fetchScene(freq) {
    try {
      const [sceneRes, linksRes] = await Promise.all([
        fetch('/api/scene'),
        fetch(`/api/links?freq=${freq}`),
      ]);

      if (!sceneRes.ok || !linksRes.ok) {
        throw new Error('Failed to fetch scene or links');
      }

      const scene = await sceneRes.json();
      const links = await linksRes.json();
      scene.links = links;

      return scene;
    } catch (e) {
      console.error('Failed to fetch scene:', e);
      return null;
    }
  }

  async function generate(type, sqft, seed) {
    const statsContent = document.getElementById('stats-content');
    if (statsContent) {
      statsContent.textContent = 'Generating...';
    }

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          building_type: type,
          total_sqft: sqft,
          seed,
          frequencies_hz: [900e6, 2.4e9],
        }),
      });

      if (res.ok) {
        const scene = await res.json();
        loadScene(scene);
      } else {
        const error = await res.text();
        if (statsContent) {
          statsContent.innerHTML = `Generation failed (HTTP ${res.status}).<br><small>${error}</small>`;
        }
      }
    } catch (e) {
      console.error('Generation error:', e);
      if (statsContent) {
        statsContent.textContent = 'Generation error: ' + e.message;
      }
    }
  }

  async function onFreqChange(freq) {
    _currentFreq = freq;
    try {
      const res = await fetch(`/api/links?freq=${freq}`);
      if (res.ok) {
        const links = await res.json();
        if (_scene) {
          _scene.links = links;
          Links.setScene(_scene);
          Filters.syncPowerRange(_scene, true);
          Filters.updateStats(_scene);
        }
      }
    } catch (e) {
      console.error('Failed to fetch links:', e);
    }
    redraw();
  }

  // Initialize on page load
  window.addEventListener('resize', resize);
  window.addEventListener('orientationchange', resize);

  resize();
  Interaction.init(canvas, tooltip, redraw);
  Filters.init(redraw, onFreqChange);

  // Load initial scene
  fetchScene(_currentFreq).then(scene => {
    if (scene) {
      loadScene(scene);
    }
  });

  return { generate };
})();
