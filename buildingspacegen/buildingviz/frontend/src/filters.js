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

  function _fmtDist(val) {
    return (val !== null && val !== undefined) ? val.toFixed(1) + ' m' : 'N/A';
  }

  function _bandLabel(freqHz) {
    if (freqHz >= 2e9) return '2.4 GHz';
    if (freqHz >= 800e6) return '900 MHz';
    return (freqHz / 1e6).toFixed(0) + ' MHz';
  }

  async function updateStats(scene) {
    if (!scene) return;

    const devices = scene.devices || [];
    const links = scene.links ? (scene.links.entries || []) : [];
    const viable = links.filter(l => l.link_viable).length;
    const mc = devices.filter(d => d.device_type === 'main_controller').length;
    const sc = devices.filter(d => d.device_type === 'secondary_controller').length;
    const s = devices.filter(d => d.device_type === 'sensor').length;

    const content = document.getElementById('stats-content');
    if (!content) return;

    // Render base stats immediately
    content.innerHTML = `
      <div><strong>Devices:</strong> ${devices.length} (${mc} MC, ${sc} SC, ${s} S)</div>
      <div><strong>Links:</strong> ${viable}/${links.length} viable</div>
      <div><strong>Building:</strong> ${scene.building ? scene.building.building_type : 'N/A'}</div>
      <div><strong>Area:</strong> ${scene.building ? scene.building.total_area_sqft.toFixed(0) : 'N/A'} sqft</div>
      <div><strong>Seed:</strong> ${scene.building ? scene.building.seed : 'N/A'}</div>
      <div id="rf-stats-placeholder" style="color:#666;margin-top:4px;">Loading RF stats...</div>
    `;

    // Fetch per-frequency stats from backend and append
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) {
        const placeholder = document.getElementById('rf-stats-placeholder');
        if (placeholder) placeholder.remove();
        return;
      }
      const stats = await res.json();
      const placeholder = document.getElementById('rf-stats-placeholder');
      if (!placeholder) return;

      const freqs = Object.keys(stats).map(Number).sort();
      if (freqs.length === 0) {
        placeholder.remove();
        return;
      }

      let html = '';
      for (const freq of freqs) {
        const band = _bandLabel(freq);
        const bs = stats[freq];
        html += `
          <div style="margin-top:6px;border-top:1px solid #0f3460;padding-top:4px;">
            <strong>${band}</strong>
            <div>Connected sensors: ${bs.sensors_with_viable_connection}/${bs.total_sensors}</div>
            <div>Range @ 97% viable: ${_fmtDist(bs.distance_97pct_m)}</div>
            <div>Range @ 70% viable: ${_fmtDist(bs.distance_70pct_m)}</div>
          </div>
        `;
      }
      placeholder.outerHTML = html;
    } catch (_) {
      const placeholder = document.getElementById('rf-stats-placeholder');
      if (placeholder) placeholder.remove();
    }
  }

  return { init, buildLegend, updateStats };
})();
