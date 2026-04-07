/**
 * Links renderer — draws RF link lines between devices.
 */

const Links = (() => {
  let _scene = null;
  let _showLinks = true;
  let _viableOnly = true;
  let _minPower = -120;
  let _maxPower = 0;
  let _highlightDeviceId = null;

  function setScene(scene) { _scene = scene; }
  function setShowLinks(v) { _showLinks = v; }
  function setViableOnly(v) { _viableOnly = v; }
  function setPowerRange(min, max) { _minPower = min; _maxPower = max; }
  function setHighlightDevice(deviceId) { _highlightDeviceId = deviceId; }

  function draw(ctx, transform) {
    if (!_scene || !_showLinks) return;

    const links = _scene.links;
    if (!links) return;

    const entries = Array.isArray(links.entries) ? links.entries : (Array.isArray(links) ? links : []);
    if (entries.length === 0) return;

    const deviceMap = {};
    for (const d of (_scene.devices || [])) {
      deviceMap[d.id] = d;
    }

    ctx.save();
    ctx.translate(transform.panX, transform.panY);
    ctx.scale(transform.scale, transform.scale);

    for (const link of entries) {
      if (_viableOnly && !link.link_viable) continue;
      if (link.rx_power_dbm < _minPower || link.rx_power_dbm > _maxPower) continue;

      const tx = deviceMap[link.tx_device_id];
      const rx = deviceMap[link.rx_device_id];
      if (!tx || !rx) continue;

      const isHighlighted = _highlightDeviceId &&
        (link.tx_device_id === _highlightDeviceId || link.rx_device_id === _highlightDeviceId);

      ctx.beginPath();
      ctx.moveTo(tx.position[0], tx.position[1]);
      ctx.lineTo(rx.position[0], rx.position[1]);
      ctx.strokeStyle = ColorMap.rxPowerToColor(link.rx_power_dbm, _minPower, _maxPower);
      ctx.lineWidth = (isHighlighted ? 2.5 : 0.8) / transform.scale;
      ctx.globalAlpha = isHighlighted ? 0.9 : 0.5;
      ctx.lineCap = 'round';
      ctx.stroke();
      ctx.globalAlpha = 1.0;
    }

    ctx.restore();
  }

  function hitTestLink(x, y, transform) {
    if (!_scene || !_scene.links) return null;

    const deviceMap = {};
    for (const d of (_scene.devices || [])) {
      deviceMap[d.id] = d;
    }

    const wx = (x - transform.panX) / transform.scale;
    const wy = (y - transform.panY) / transform.scale;
    const hitDist = 3 / transform.scale;

    const links = _scene.links;
    const entries = Array.isArray(links.entries) ? links.entries : (Array.isArray(links) ? links : []);

    for (const link of entries) {
      const tx = deviceMap[link.tx_device_id];
      const rx = deviceMap[link.rx_device_id];
      if (!tx || !rx) continue;

      const d = _pointToSegmentDist(
        wx, wy,
        tx.position[0], tx.position[1],
        rx.position[0], rx.position[1]
      );

      if (d < hitDist) return link;
    }

    return null;
  }

  function _pointToSegmentDist(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const lenSq = dx * dx + dy * dy;

    if (lenSq === 0) return Math.hypot(px - ax, py - ay);

    let t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));

    const closestX = ax + t * dx;
    const closestY = ay + t * dy;
    return Math.hypot(px - closestX, py - closestY);
  }

  return {
    setScene,
    setShowLinks,
    setViableOnly,
    setPowerRange,
    setHighlightDevice,
    draw,
    hitTestLink,
  };
})();
