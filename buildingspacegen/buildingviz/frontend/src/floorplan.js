/**
 * Floor plan renderer — draws rooms, walls, and doors onto Canvas 2D context.
 */

const FloorPlan = (() => {
  let _scene = null;
  let _showLabels = false;

  function setScene(scene) { _scene = scene; }
  function setShowLabels(show) { _showLabels = show; }

  function draw(ctx, transform, floorIndex = 0) {
    if (!_scene || !_scene.building) return;
    const floor = _scene.building.floors[floorIndex];
    if (!floor) return;

    ctx.save();
    ctx.translate(transform.panX, transform.panY);
    ctx.scale(transform.scale, transform.scale);

    // Draw room fills and borders
    for (const room of floor.rooms) {
      const poly = room.polygon;
      if (!poly || poly.length < 3) continue;

      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
      ctx.closePath();

      ctx.fillStyle = ColorMap.roomTypeToFillColor(room.room_type);
      ctx.fill();
      ctx.strokeStyle = ColorMap.roomTypeToBorderColor(room.room_type);
      ctx.lineWidth = 0.4 / transform.scale;
      ctx.stroke();
    }

    // Draw walls
    for (const wall of floor.walls) {
      const mat = wall.materials && wall.materials[0] ? wall.materials[0].name : 'gypsum_double';
      ctx.beginPath();
      ctx.moveTo(wall.start[0], wall.start[1]);
      ctx.lineTo(wall.end[0], wall.end[1]);
      ctx.strokeStyle = ColorMap.materialToColor(mat);
      ctx.lineWidth = ColorMap.materialToLineWidth(mat, wall.is_exterior) / transform.scale;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.stroke();
    }

    // Draw doors
    for (const door of floor.doors) {
      const wall = floor.walls.find(w => w.id === door.wall_id);
      if (!wall) continue;
      const dx = wall.end[0] - wall.start[0];
      const dy = wall.end[1] - wall.start[1];
      const px = wall.start[0] + dx * door.position_along_wall;
      const py = wall.start[1] + dy * door.position_along_wall;

      ctx.beginPath();
      ctx.arc(px, py, 0.35, 0, Math.PI * 2);
      ctx.fillStyle = ColorMap.materialToColor(door.material ? door.material.name : 'wood_door');
      ctx.fill();
    }

    // Draw room labels
    if (_showLabels) {
      for (const room of floor.rooms) {
        const poly = room.polygon;
        if (!poly || poly.length < 3) continue;

        // Compute centroid
        let cx = 0, cy = 0;
        for (const p of poly) { cx += p[0]; cy += p[1]; }
        cx /= poly.length;
        cy /= poly.length;

        ctx.fillStyle = '#333';
        ctx.font = `${Math.max(0.6, 0.8 / transform.scale)}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const label = room.room_type.replace(/_/g, ' ');
        ctx.fillText(label, cx, cy - 0.3 / transform.scale);

        ctx.fillStyle = '#666';
        ctx.font = `${Math.max(0.4, 0.6 / transform.scale)}px sans-serif`;
        ctx.fillText(`${room.area_sqft.toFixed(0)} sqft`, cx, cy + 0.5 / transform.scale);
      }
    }

    ctx.restore();
  }

  function hitTestRoom(x, y, transform, floorIndex = 0) {
    if (!_scene) return null;
    const floor = _scene.building.floors[floorIndex];
    if (!floor) return null;

    const wx = (x - transform.panX) / transform.scale;
    const wy = (y - transform.panY) / transform.scale;

    for (const room of floor.rooms) {
      if (_pointInPolygon(wx, wy, room.polygon)) return room;
    }
    return null;
  }

  function _pointInPolygon(x, y, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], yi = poly[i][1];
      const xj = poly[j][0], yj = poly[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
        inside = !inside;
      }
    }
    return inside;
  }

  return { setScene, setShowLabels, draw, hitTestRoom };
})();
