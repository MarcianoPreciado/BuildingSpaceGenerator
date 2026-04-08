/**
 * Interaction handler — pan, zoom, hover, click.
 * Does NOT reference Canvas 2D context; works with abstract coordinates.
 */

const Interaction = (() => {
  let _canvas = null;
  let _transform = { panX: 0, panY: 0, scale: 20 };
  let _isDragging = false;
  let _lastMouse = { x: 0, y: 0 };
  let _tooltip = null;
  let _onRedraw = null;
  let _scene = null;

  function init(canvas, tooltip, onRedraw) {
    _canvas = canvas;
    _tooltip = tooltip;
    _onRedraw = onRedraw;

    canvas.addEventListener('wheel', _onWheel, { passive: false });
    canvas.addEventListener('mousedown', _onMouseDown);
    canvas.addEventListener('mousemove', _onMouseMove);
    canvas.addEventListener('mouseup', _onMouseUp);
    canvas.addEventListener('mouseleave', _hideTooltip);
    canvas.addEventListener('click', _onClick);
  }

  function setScene(scene) { _scene = scene; }
  function getTransform() { return { ..._transform }; }

  function fitToScene(canvasWidth, canvasHeight) {
    if (!_scene || !_scene.building || !_scene.building.floors.length) return;

    const fp = _scene.building.floors[0].footprint;
    if (!fp || !fp.length) return;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of fp) {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }

    const bw = maxX - minX;
    const bh = maxY - minY;
    const margin = 0.9;
    const scale = Math.min(
      (canvasWidth * margin) / bw,
      (canvasHeight * margin) / bh
    );

    _transform.scale = scale;
    _transform.panX = (canvasWidth - bw * scale) / 2 - minX * scale;
    _transform.panY = (canvasHeight - bh * scale) / 2 - minY * scale;
  }

  function _onWheel(e) {
    e.preventDefault();
    const rect = _canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.1 : 0.9;

    _transform.panX = mx - (mx - _transform.panX) * factor;
    _transform.panY = my - (my - _transform.panY) * factor;
    _transform.scale *= factor;
    _onRedraw();
  }

  function _onMouseDown(e) {
    _isDragging = true;
    _lastMouse = { x: e.clientX, y: e.clientY };
    _canvas.style.cursor = 'grabbing';
  }

  function _onMouseMove(e) {
    const rect = _canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (_isDragging) {
      _transform.panX += e.clientX - _lastMouse.x;
      _transform.panY += e.clientY - _lastMouse.y;
      _lastMouse = { x: e.clientX, y: e.clientY };
      _onRedraw();
      return;
    }

    // Hover hit testing
    const device = Devices.hitTestDevice(mx, my, _transform);
    if (device) {
      _showDeviceTooltip(device, e.clientX, e.clientY);
      _canvas.style.cursor = 'pointer';
      return;
    }

    const link = Links.hitTestLink(mx, my, _transform);
    if (link) {
      _showLinkTooltip(link, e.clientX, e.clientY);
      _canvas.style.cursor = 'crosshair';
      return;
    }

    _hideTooltip();
    _canvas.style.cursor = 'grab';
  }

  function _onMouseUp() {
    _isDragging = false;
    _canvas.style.cursor = 'grab';
  }

  function _onClick(e) {
    const rect = _canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const device = Devices.hitTestDevice(mx, my, _transform);
    if (device) {
      Devices.setSelected(device.id);
      Links.setHighlightDevice(device.id);
    } else {
      Devices.setSelected(null);
      Links.setHighlightDevice(null);
    }
    _onRedraw();
  }

  function _currentFrequency() {
    return _scene && _scene.links ? _scene.links.frequency_hz : null;
  }

  function _deviceById(deviceId) {
    if (!_scene || !_scene.devices) return null;
    return _scene.devices.find(device => device.id === deviceId) || null;
  }

  function _isController(device) {
    return device && (
      device.device_type === 'main_controller' ||
      device.device_type === 'secondary_controller'
    );
  }

  function _bestControllerLink(device) {
    if (!_scene || !_scene.links || device.device_type !== 'sensor') return null;

    const entries = Array.isArray(_scene.links.entries) ? _scene.links.entries : [];
    let best = null;

    for (const link of entries) {
      const includesSensor = link.tx_device_id === device.id || link.rx_device_id === device.id;
      if (!includesSensor) continue;

      const peerId = link.tx_device_id === device.id ? link.rx_device_id : link.tx_device_id;
      const peerDevice = _deviceById(peerId);
      if (!_isController(peerDevice)) continue;

      if (best === null || link.rx_power_dbm > best.link.rx_power_dbm) {
        best = { link, peerDevice };
      }
    }

    return best;
  }

  function _simulationSettingsForFrequency(freq) {
    if (!Number.isFinite(freq) || !_scene || !_scene.simulation || !_scene.simulation.per_frequency) {
      return null;
    }
    return _scene.simulation.per_frequency[String(Math.trunc(freq))] || null;
  }

  function _showDeviceTooltip(device, cx, cy) {
    const profile = _scene && _scene.radio_profiles && _scene.radio_profiles[device.radio_profile_name];
    const freqs = profile
      ? profile.supported_frequencies_hz.map(f => `${(f / 1e6).toFixed(0)} MHz`).join(', ')
      : 'N/A';
    const currentFreq = _currentFrequency();
    const bestControllerLink = _bestControllerLink(device);
    const simulationSettings = _simulationSettingsForFrequency(currentFreq);

    _tooltip.style.display = 'block';
    _tooltip.style.left = (cx + 12) + 'px';
    _tooltip.style.top = (cy - 10) + 'px';

    const devTypeLabel = device.device_type.replace(/_/g, ' ').toUpperCase();
    const controllerLinkRow = device.device_type === 'sensor'
      ? (() => {
          if (!bestControllerLink) {
            return '<div class="tt-row"><strong>Controller Link:</strong> No current-band controller link</div>';
          }
          const { link, peerDevice } = bestControllerLink;
          const status = link.link_viable ? 'Viable' : 'Not viable';
          const rxPower = Number.isFinite(link.rx_power_dbm) ? `${link.rx_power_dbm.toFixed(1)} dBm` : 'N/A';
          const margin = Number.isFinite(link.link_margin_db) ? `${link.link_margin_db.toFixed(1)} dB` : 'N/A';
          return `
            <div class="tt-row"><strong>Controller Link:</strong> ${status}</div>
            <div class="tt-row"><strong>Controller:</strong> ${peerDevice ? peerDevice.id : 'Unknown'}</div>
            <div class="tt-row"><strong>RX Power:</strong> ${rxPower}</div>
            <div class="tt-row"><strong>Margin:</strong> ${margin}</div>
          `;
        })()
      : '';
    const simulationRow = simulationSettings
      ? `
        <div class="tt-row"><strong>Sim TX:</strong> ${simulationSettings.tx_power_dbm.toFixed(1)} dBm</div>
        <div class="tt-row"><strong>Sensor TX Gain:</strong> ${simulationSettings.sensor_tx_antenna_gain_dbi.toFixed(1)} dBi</div>
        <div class="tt-row"><strong>Controller RX Gain:</strong> ${simulationSettings.controller_rx_antenna_gain_dbi.toFixed(1)} dBi</div>
        <div class="tt-row"><strong>Min RSSI:</strong> ${simulationSettings.min_rssi_dbm.toFixed(1)} dBm</div>
      `
      : '';
    _tooltip.innerHTML = `
      <div class="tt-title">${devTypeLabel}</div>
      <div class="tt-row"><strong>ID:</strong> ${device.id}</div>
      <div class="tt-row"><strong>Room:</strong> ${device.room_id}</div>
      <div class="tt-row"><strong>Pos:</strong> (${device.position[0].toFixed(1)}, ${device.position[1].toFixed(1)}, ${device.position[2].toFixed(1)}m)</div>
      <div class="tt-row"><strong>Profile:</strong> ${device.radio_profile_name}</div>
      <div class="tt-row"><strong>Freqs:</strong> ${freqs}</div>
      ${Number.isFinite(currentFreq) ? `<div class="tt-row"><strong>Current Band:</strong> ${(currentFreq / 1e6).toFixed(0)} MHz</div>` : ''}
      ${controllerLinkRow}
      ${simulationRow}
      ${profile ? `<div class="tt-row"><strong>Profile TX:</strong> ${profile.tx_power_dbm} dBm | <strong>Profile RX Sens:</strong> ${profile.rx_sensitivity_dbm} dBm</div>` : ''}
    `;
  }

  function _showLinkTooltip(link, cx, cy) {
    _tooltip.style.display = 'block';
    _tooltip.style.left = (cx + 12) + 'px';
    _tooltip.style.top = (cy - 10) + 'px';

    _tooltip.innerHTML = `
      <div class="tt-title">RF LINK</div>
      <div class="tt-row"><strong>TX:</strong> ${link.tx_device_id}</div>
      <div class="tt-row"><strong>RX:</strong> ${link.rx_device_id}</div>
      <div class="tt-row"><strong>Distance:</strong> ${link.distance_m ? link.distance_m.toFixed(1) : '?'} m</div>
      <div class="tt-row"><strong>Path loss:</strong> ${link.path_loss_db ? link.path_loss_db.toFixed(1) : '?'} dB</div>
      <div class="tt-row"><strong>RX power:</strong> ${link.rx_power_dbm ? link.rx_power_dbm.toFixed(1) : '?'} dBm</div>
      <div class="tt-row"><strong>Walls:</strong> ${link.walls_crossed !== undefined ? link.walls_crossed : '?'}</div>
      <div class="tt-row"><strong>Viable:</strong> ${link.link_viable ? 'Yes' : 'No'} | <strong>Margin:</strong> ${link.link_margin_db ? link.link_margin_db.toFixed(1) : '?'} dB</div>
    `;
  }

  function _hideTooltip() {
    if (_tooltip) _tooltip.style.display = 'none';
  }

  return { init, setScene, getTransform, fitToScene };
})();
