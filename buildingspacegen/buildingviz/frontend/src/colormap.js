/**
 * Color mapping utilities for the BuildingSpaceGenerator visualizer.
 * Works with data → CSS color strings (no Canvas 2D context).
 */

const ColorMap = (() => {
  const ROOM_COLORS = {
    open_office: '#4CAF50',
    private_office: '#2196F3',
    conference: '#FFC107',
    lobby: '#9C27B0',
    corridor: '#607D8B',
    restroom: '#009688',
    kitchen_break: '#FF5722',
    mechanical: '#455A64',
    it_server: '#37474F',
    storage: '#795548',
    warehouse_bay: '#8BC34A',
    loading_dock: '#CDDC39',
    stairwell: '#78909C',
    elevator: '#546E7A',
  };

  /**
   * Map rx_power_dbm to a CSS color string (green=strong, red=weak).
   */
  function rxPowerToColor(dbm, minDbm = -100, maxDbm = -40) {
    const t = Math.max(0, Math.min(1, (dbm - minDbm) / (maxDbm - minDbm)));
    // Green → Yellow → Red gradient
    if (t > 0.5) {
      // Yellow to Red
      const s = (t - 0.5) * 2;
      const r = Math.round(255 * (1 - s));
      return `rgba(${r}, 200, 40, 0.7)`;
    } else {
      // Green to Yellow
      const s = t * 2;
      const g = Math.round(200 * s);
      return `rgba(220, ${g}, 40, 0.7)`;
    }
  }

  function roomTypeToFillColor(roomType) {
    const fills = {
      open_office: 'rgba(76,175,80,0.15)',
      private_office: 'rgba(33,150,243,0.15)',
      conference: 'rgba(255,193,7,0.20)',
      lobby: 'rgba(156,39,176,0.15)',
      corridor: 'rgba(96,125,139,0.12)',
      restroom: 'rgba(0,150,136,0.15)',
      kitchen_break: 'rgba(255,87,34,0.15)',
      mechanical: 'rgba(69,90,100,0.20)',
      it_server: 'rgba(55,71,79,0.25)',
      storage: 'rgba(121,85,72,0.15)',
      warehouse_bay: 'rgba(139,195,74,0.15)',
      loading_dock: 'rgba(205,220,57,0.20)',
      stairwell: 'rgba(120,144,156,0.20)',
      elevator: 'rgba(84,110,122,0.25)',
    };
    return fills[roomType] || 'rgba(200,200,200,0.12)';
  }

  function roomTypeToBorderColor(roomType) {
    return ROOM_COLORS[roomType] || '#999';
  }

  function materialToColor(materialName) {
    const colors = {
      gypsum_single: 'rgba(180,180,180,0.9)',
      gypsum_double: 'rgba(150,150,150,0.9)',
      concrete_block: 'rgba(90,90,90,0.9)',
      reinforced_concrete: 'rgba(60,60,60,0.95)',
      brick: 'rgba(141,110,99,0.9)',
      glass_standard: 'rgba(129,212,250,0.7)',
      glass_low_e: 'rgba(79,195,247,0.8)',
      wood_door: 'rgba(161,136,127,0.9)',
      metal_fire_door: 'rgba(84,110,122,0.95)',
      elevator_shaft: 'rgba(55,71,79,1.0)',
    };
    return colors[materialName] || 'rgba(150,150,150,0.8)';
  }

  function materialToLineWidth(materialName, isExterior) {
    if (isExterior) return 3.5;
    if (materialName.includes('concrete') || materialName === 'brick') return 2.5;
    if (materialName.includes('glass')) return 1.5;
    return 1.5;
  }

  function deviceTypeToShape(deviceType) {
    const shapes = {
      main_controller: { type: 'diamond', size: 14, fill: '#e94560', stroke: '#fff' },
      secondary_controller: { type: 'square', size: 10, fill: '#4FC3F7', stroke: '#fff' },
      sensor: { type: 'circle', size: 6, fill: '#81C784', stroke: '#fff' },
    };
    return shapes[deviceType] || { type: 'circle', size: 6, fill: '#aaa', stroke: '#fff' };
  }

  function deviceFill(device, defaultFill, scene) {
    if (device.device_type !== 'sensor') return defaultFill;

    const metadata = device.metadata || {};
    const currentFrequency = scene && scene.links ? scene.links.frequency_hz : null;

    if (Number.isFinite(currentFrequency) && Array.isArray(metadata.viable_controller_link_frequencies_hz)) {
      return metadata.viable_controller_link_frequencies_hz.includes(currentFrequency)
        ? defaultFill
        : '#ef4444';
    }

    if (metadata.has_viable_controller_link === false) {
      return '#ef4444';
    }

    if (scene && scene.links && Array.isArray(scene.links.entries) && Array.isArray(scene.devices)) {
      const deviceMap = Object.fromEntries(scene.devices.map(entry => [entry.id, entry]));
      const controllerLinks = scene.links.entries.filter(link => {
        if (link.tx_device_id !== device.id && link.rx_device_id !== device.id) return false;
        const peerId = link.tx_device_id === device.id ? link.rx_device_id : link.tx_device_id;
        const peer = deviceMap[peerId];
        return peer && (peer.device_type === 'main_controller' || peer.device_type === 'secondary_controller');
      });

      if (controllerLinks.length > 0) {
        return controllerLinks.some(link => link.link_viable) ? defaultFill : '#ef4444';
      }
    }

    return defaultFill;
  }

  return {
    rxPowerToColor,
    roomTypeToFillColor,
    roomTypeToBorderColor,
    materialToColor,
    materialToLineWidth,
    deviceTypeToShape,
    deviceFill,
    ROOM_COLORS,
  };
})();
