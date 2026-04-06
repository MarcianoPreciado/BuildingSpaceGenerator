/**
 * Filter controls — wires UI controls to renderer state.
 * Does NOT reference Canvas 2D context; fully reusable for Phase 2 (Three.js).
 */

const Filters = (() => {
  let _onRedraw = null;
  let _onFreqChange = null;

  function init(onRedraw, onFreqChange) {
    _onRedraw = onRedraw;
    _onFreqChange = onFreqChange;

    document.getElementById('freq-select').addEventListener('change', e => {
      _onFreqChange(parseFloat(e.target.value));
    });

    document.getElementById('min-power').addEventListener('input', e => {
      document.getElementById('min-power-val').textContent = e.target.value;
      _updatePowerFilter();
    });

    document.getElementById('max-power').addEventListener('input', e => {
      document.getElementById('max-power-val').textContent = e.target.value;
      _updatePowerFilter();
    });

    document.getElementById('show-viable').addEventListener('change', e => {
      Links.setViableOnly(e.target.checked);
      _onRedraw();
    });

    document.getElementById('show-links').addEventListener('change', e => {
      Links.setShowLinks(e.target.checked);
      _onRedraw();
    });

    document.getElementById('show-sensors').addEventListener('change', e => {
      Devices.setVisibility('sensor', e.target.checked);
      _onRedraw();
    });

    document.getElementById('show-secondary').addEventListener('change', e => {
      Devices.setVisibility('secondary_controller', e.target.checked);
      _onRedraw();
    });

    document.getElementById('show-main').addEventListener('change', e => {
      Devices.setVisibility('main_controller', e.target.checked);
      _onRedraw();
    });

    document.getElementById('show-labels').addEventListener('change', e => {
      FloorPlan.setShowLabels(e.target.checked);
      _onRedraw();
    });

    document.getElementById('gen-btn').addEventListener('click', () => {
      const type = document.getElementById('gen-type').value;
      const sqft = parseFloat(document.getElementById('gen-sqft').value);
      const seed = parseInt(document.getElementById('gen-seed').value);
      if (window.App && window.App.generate) {
        window.App.generate(type, sqft, seed);
      }
    });
  }

  function _updatePowerFilter() {
    const min = parseFloat(document.getElementById('min-power').value);
    const max = parseFloat(document.getElementById('max-power').value);
    Links.setPowerRange(min, max);
    _onRedraw();
  }

  function buildLegend(scene) {
    if (!scene || !scene.building) return;

    const container = document.getElementById('legend-rooms');
    container.innerHTML = '';
    const seen = new Set();

    for (const floor of scene.building.floors) {
      for (const room of floor.rooms) {
        if (!seen.has(room.room_type)) {
          seen.add(room.room_type);
          const color = ColorMap.roomTypeToBorderColor(room.room_type);
          const item = document.createElement('div');
          item.className = 'legend-item';
          item.innerHTML = `
            <div class="legend-swatch" style="background:${color};"></div>
            <span>${room.room_type.replace(/_/g, ' ')}</span>
          `;
          container.appendChild(item);
        }
      }
    }
  }

  function updateStats(scene) {
    if (!scene) return;

    const devices = scene.devices || [];
    const links = scene.links ? (scene.links.entries || []) : [];
    const viable = links.filter(l => l.link_viable).length;
    const mc = devices.filter(d => d.device_type === 'main_controller').length;
    const sc = devices.filter(d => d.device_type === 'secondary_controller').length;
    const s = devices.filter(d => d.device_type === 'sensor').length;

    const content = document.getElementById('stats-content');
    if (content) {
      content.innerHTML = `
        <div><strong>Devices:</strong> ${devices.length} (${mc} MC, ${sc} SC, ${s} S)</div>
        <div><strong>Links:</strong> ${viable}/${links.length} viable</div>
        <div><strong>Building:</strong> ${scene.building ? scene.building.building_type : 'N/A'}</div>
        <div><strong>Area:</strong> ${scene.building ? scene.building.total_area_sqft.toFixed(0) : 'N/A'} sqft</div>
        <div><strong>Seed:</strong> ${scene.building ? scene.building.seed : 'N/A'}</div>
      `;
    }
  }

  return { init, buildLegend, updateStats };
})();
