/**
 * Device renderer — draws sensors and controllers onto Canvas 2D context.
 */

const Devices = (() => {
  let _scene = null;
  let _visibleTypes = {
    main_controller: true,
    secondary_controller: true,
    sensor: true,
  };
  let _selectedDeviceId = null;

  function setScene(scene) { _scene = scene; }
  function setVisibility(type, visible) { _visibleTypes[type] = visible; }
  function setSelected(deviceId) { _selectedDeviceId = deviceId; }

  function draw(ctx, transform) {
    if (!_scene || !_scene.devices) return;

    ctx.save();
    ctx.translate(transform.panX, transform.panY);
    ctx.scale(transform.scale, transform.scale);

    for (const device of _scene.devices) {
      if (!_visibleTypes[device.device_type]) continue;

      const shape = ColorMap.deviceTypeToShape(device.device_type);
      const dx = device.position[0];
      const dy = device.position[1];
      const r = shape.size / transform.scale;
      const isSelected = device.id === _selectedDeviceId;

      ctx.beginPath();
      if (shape.type === 'circle') {
        ctx.arc(dx, dy, r, 0, Math.PI * 2);
      } else if (shape.type === 'square') {
        ctx.rect(dx - r, dy - r, r * 2, r * 2);
      } else if (shape.type === 'diamond') {
        ctx.moveTo(dx, dy - r * 1.3);
        ctx.lineTo(dx + r, dy);
        ctx.lineTo(dx, dy + r * 1.3);
        ctx.lineTo(dx - r, dy);
        ctx.closePath();
      }

      ctx.fillStyle = isSelected ? '#FFD700' : shape.fill;
      ctx.fill();
      ctx.strokeStyle = shape.stroke;
      ctx.lineWidth = (isSelected ? 2.5 : 1.2) / transform.scale;
      ctx.stroke();

      // Add glow effect for selected devices
      if (isSelected) {
        ctx.strokeStyle = 'rgba(255, 215, 0, 0.5)';
        ctx.lineWidth = (5) / transform.scale;
        ctx.stroke();
      }
    }

    ctx.restore();
  }

  function hitTestDevice(x, y, transform) {
    if (!_scene) return null;

    const wx = (x - transform.panX) / transform.scale;
    const wy = (y - transform.panY) / transform.scale;

    let closest = null;
    let closestDist = Infinity;

    for (const device of _scene.devices) {
      if (!_visibleTypes[device.device_type]) continue;

      const shape = ColorMap.deviceTypeToShape(device.device_type);
      const hitRadius = (shape.size + 4) / transform.scale;
      const dx = device.position[0];
      const dy = device.position[1];
      const dist = Math.hypot(wx - dx, wy - dy);

      if (dist < hitRadius && dist < closestDist) {
        closest = device;
        closestDist = dist;
      }
    }

    return closest;
  }

  return { setScene, setVisibility, setSelected, draw, hitTestDevice };
})();
