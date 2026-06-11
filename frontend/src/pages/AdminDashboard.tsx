import React, { useState, useEffect, useRef } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { Battery, Cpu, Map as MapIcon, Package, LogOut, Navigation, Settings, Activity, Edit2, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { configApi, inventoryApi } from '../services/api';

export const AdminDashboard: React.FC = () => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [telemetry, setTelemetry] = useState({ battery: 100, cpu_temp: 40, x: 0, y: 0, status: 'Idle', mission: 'Standby', rack_status: ["locked", "locked", "locked", "locked"] });
  const [logs, setLogs] = useState<{ time: string, event: string, type: 'info' | 'success' | 'warning' }[]>([]);
  const [activeTab, setActiveTab] = useState('live_map');
  const [config, setConfig] = useState<any>({ max_speed: 1.0, safe_mode: true, maintenance_mode: false, telemetry_frequency: 1000 });
  const wsRef = useRef<WebSocket | null>(null);

  // Inventory State
  const [inventoryItems, setInventoryItems] = useState<any[]>([]);
  const [isInventoryModalOpen, setIsInventoryModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<any | null>(null);
  const [inventoryFormData, setInventoryFormData] = useState({ name: '', description: '', quantity: 1, rack_id: '' });

  const loadInventory = async () => {
    try {
      const data = await inventoryApi.getInventory();
      setInventoryItems(data);
    } catch (err) {
      console.error('Failed to load inventory', err);
    }
  };

  useEffect(() => {
    if (activeTab === 'inventory') {
      loadInventory();
    }
  }, [activeTab]);

  const handleInventorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...inventoryFormData,
        rack_id: inventoryFormData.rack_id ? parseInt(inventoryFormData.rack_id as string) : null,
      };

      if (editingItem) {
        await inventoryApi.updateItem(editingItem.id, payload);
      } else {
        await inventoryApi.createItem(payload);
      }
      setIsInventoryModalOpen(false);
      setEditingItem(null);
      loadInventory();
      
      const newLog = {
        time: new Date().toLocaleTimeString(),
        event: editingItem ? `Inventory item '${payload.name}' updated` : `New inventory item '${payload.name}' added`,
        type: 'success' as const
      };
      setLogs(prev => [newLog, ...prev].slice(0, 15));
    } catch (err) {
      console.error('Failed to save item', err);
      alert('Failed to save inventory item.');
    }
  };
  
  const handleInventoryDelete = async (id: number, name: string) => {
    if (!window.confirm(`Are you sure you want to delete ${name}?`)) return;
    try {
      await inventoryApi.deleteItem(id);
      loadInventory();
      const newLog = {
        time: new Date().toLocaleTimeString(),
        event: `Inventory item '${name}' deleted`,
        type: 'warning' as const
      };
      setLogs(prev => [newLog, ...prev].slice(0, 15));
    } catch (err) {
      console.error('Failed to delete item', err);
      alert('Failed to delete item.');
    }
  };

  const openAddInventoryModal = () => {
    setEditingItem(null);
    setInventoryFormData({ name: '', description: '', quantity: 1, rack_id: '' });
    setIsInventoryModalOpen(true);
  };

  const openEditInventoryModal = (item: any) => {
    setEditingItem(item);
    setInventoryFormData({ name: item.name, description: item.description || '', quantity: item.quantity, rack_id: item.rack_id?.toString() || '' });
    setIsInventoryModalOpen(true);
  };

  useEffect(() => {
    // Fetch initial config
    configApi.getConfig().then(setConfig).catch(console.error);

    // Connect to WebSocket using the current hostname
    const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/ui`);
    wsRef.current = ws;

    ws.onopen = () => console.log('Connected to Backend UI WebSocket');
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'telemetry') {
          setTelemetry({
            battery: data.battery,
            cpu_temp: data.cpu_temp,
            x: data.x,
            y: data.y,
            status: data.status,
            mission: data.mission,
            rack_status: data.rack_status || ["locked", "locked", "locked", "locked"]
          });
          if (data.log) {
            const logType: 'info' | 'success' | 'warning' = data.log.includes('warning') ? 'warning' : data.log.includes('Obstacle') ? 'warning' : data.log.includes('confirmed') ? 'success' : 'info';
            const newLog = {
              time: data.timestamp || new Date().toLocaleTimeString(),
              event: data.log,
              type: logType
            };
            setLogs(prev => [newLog, ...prev].slice(0, 15));
          }
        } else if (data.type === 'config_update') {
          setConfig(data.config);
          const newLog = {
            time: new Date().toLocaleTimeString(),
            event: 'System configuration remotely updated',
            type: 'info' as const
          };
          setLogs(prev => [newLog, ...prev].slice(0, 15));
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };

    ws.onclose = () => console.log('Disconnected from Backend UI WebSocket');

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getBatteryColor = (level: number) => {
    if (level > 50) return 'var(--accent-green)';
    if (level > 20) return 'var(--accent-cyan)';
    return 'var(--accent-red)';
  };

  const mapX = `${50 + (telemetry.x / 5) * 50}%`;
  const mapY = `${50 - (telemetry.y / 5) * 50}%`;

  const handleConfigChange = async (key: string, value: any) => {
    const updated = { ...config, [key]: value };
    setConfig(updated); // Optimistic UI update
    try {
      await configApi.updateConfig({ [key]: value });
    } catch (err) {
      console.error(err);
      // Revert if failed (optional, let's keep it simple for now)
    }
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '2rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '1.2rem', boxShadow: '0 0 15px var(--accent-blue-glow)' }}>
            {user?.username.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', margin: 0 }}>{user?.username}</h3>
            <span style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>{user?.role} Access</span>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <button 
            className="btn" 
            style={{ background: activeTab === 'live_map' ? 'rgba(37, 99, 235, 0.2)' : 'transparent', color: activeTab === 'live_map' ? '#fff' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '16px', border: activeTab === 'live_map' ? '1px solid var(--accent-blue)' : '1px solid transparent', boxShadow: activeTab === 'live_map' ? '0 0 15px var(--accent-blue-glow)' : 'none' }}
            onClick={() => setActiveTab('live_map')}
          >
            <MapIcon size={20} color={activeTab === 'live_map' ? 'var(--accent-cyan)' : 'var(--text-secondary)'} />
            <span>Live Map & Telemetry</span>
          </button>
          <button 
            className="btn" 
            style={{ background: activeTab === 'inventory' ? 'rgba(37, 99, 235, 0.2)' : 'transparent', color: activeTab === 'inventory' ? '#fff' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '16px', border: activeTab === 'inventory' ? '1px solid var(--accent-blue)' : '1px solid transparent', boxShadow: activeTab === 'inventory' ? '0 0 15px var(--accent-blue-glow)' : 'none' }}
            onClick={() => setActiveTab('inventory')}
          >
            <Package size={20} color={activeTab === 'inventory' ? 'var(--accent-cyan)' : 'var(--text-secondary)'} />
            <span>Inventory Management</span>
          </button>
          <button 
            className="btn" 
            style={{ background: activeTab === 'system' ? 'rgba(37, 99, 235, 0.2)' : 'transparent', color: activeTab === 'system' ? '#fff' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '16px', border: activeTab === 'system' ? '1px solid var(--accent-blue)' : '1px solid transparent', boxShadow: activeTab === 'system' ? '0 0 15px var(--accent-blue-glow)' : 'none' }}
            onClick={() => setActiveTab('system')}
          >
            <Settings size={20} color={activeTab === 'system' ? 'var(--accent-cyan)' : 'var(--text-secondary)'} />
            <span>System Configuration</span>
          </button>
        </nav>

        <div style={{ marginTop: 'auto' }}>
          <button onClick={handleLogout} className="btn" style={{ width: '100%', background: 'rgba(244, 63, 94, 0.1)', color: 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
            <LogOut size={20} />
            <span>Disconnect</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem' }}>
          <div>
            <h2 style={{ fontSize: '2rem', background: 'linear-gradient(to right, #fff, var(--text-secondary))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Command Center
            </h2>
            <span style={{ color: 'var(--text-secondary)' }}>Monitoring and managing robotic operations</span>
          </div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <div className="flex-center" style={{ gap: '10px', background: 'rgba(16, 185, 129, 0.1)', padding: '10px 20px', borderRadius: '30px', color: 'var(--accent-green)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <div className="status-indicator"></div>
              <span style={{ fontWeight: 600, letterSpacing: '0.5px' }}>System Online</span>
            </div>
            {config.maintenance_mode && (
              <div className="flex-center animate-slide-up" style={{ gap: '10px', background: 'rgba(244, 63, 94, 0.1)', padding: '10px 20px', borderRadius: '30px', color: 'var(--accent-red)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
                <Activity size={18} className="spinner" />
                <span style={{ fontWeight: 600, letterSpacing: '0.5px' }}>Maintenance Mode</span>
              </div>
            )}
          </div>
        </header>

        <AnimatePresence mode="wait">
          {activeTab === 'live_map' && (
            <motion.div key="live_map" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
              <div className="grid-cols-4" style={{ marginBottom: '2rem' }}>
                <GlassPanel className="hover-scale">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
                    <div style={{ background: 'rgba(6, 182, 212, 0.2)', padding: '14px', borderRadius: '16px', color: 'var(--accent-cyan)', boxShadow: 'inset 0 0 10px rgba(6,182,212,0.1)' }}>
                      <Battery size={28} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px' }}>Power Level</div>
                      <div className="mono" style={{ fontSize: '1.8rem', fontWeight: 700 }}>{telemetry.battery}%</div>
                    </div>
                  </div>
                  <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${telemetry.battery}%`, background: getBatteryColor(telemetry.battery), transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)', boxShadow: `0 0 10px ${getBatteryColor(telemetry.battery)}` }}></div>
                  </div>
                </GlassPanel>

                <GlassPanel className="hover-scale">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
                    <div style={{ background: 'rgba(244, 63, 94, 0.2)', padding: '14px', borderRadius: '16px', color: 'var(--accent-red)', boxShadow: 'inset 0 0 10px rgba(244, 63, 94,0.1)' }}>
                      <Cpu size={28} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px' }}>Thermal Core</div>
                      <div className="mono" style={{ fontSize: '1.8rem', fontWeight: 700 }}>{telemetry.cpu_temp}°C</div>
                    </div>
                  </div>
                   <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.min(100, (telemetry.cpu_temp / 80) * 100)}%`, background: telemetry.cpu_temp > 70 ? 'var(--accent-red)' : 'var(--accent-blue)', transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)' }}></div>
                  </div>
                </GlassPanel>

                <GlassPanel className="hover-scale">
                   <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ background: 'rgba(37, 99, 235, 0.2)', padding: '14px', borderRadius: '16px', color: 'var(--accent-blue)', boxShadow: 'inset 0 0 10px rgba(37, 99, 235, 0.1)' }}>
                      <Navigation size={28} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px' }}>Status</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 600, color: telemetry.status === 'Idle' ? 'var(--text-primary)' : 'var(--accent-cyan)' }}>{telemetry.status}</div>
                    </div>
                  </div>
                </GlassPanel>

                <GlassPanel className="hover-scale">
                   <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ background: 'rgba(16, 185, 129, 0.2)', padding: '14px', borderRadius: '16px', color: 'var(--accent-green)', boxShadow: 'inset 0 0 10px rgba(16, 185, 129,0.1)' }}>
                      <Package size={28} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px' }}>Active Racks</div>
                      <div className="mono" style={{ fontSize: '1.8rem', fontWeight: 700 }}>{telemetry.rack_status.filter(s => s === 'unlocked').length} <span style={{fontSize: '1rem', color: 'var(--text-secondary)'}}>/ 4</span></div>
                    </div>
                  </div>
                </GlassPanel>
              </div>

              <div className="grid-cols-2">
                <GlassPanel style={{ minHeight: '450px', display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                    <h3 style={{ margin: 0 }}>Navigational Map</h3>
                    <div className="mono" style={{ fontSize: '0.9rem', color: 'var(--accent-cyan)', background: 'rgba(6, 182, 212, 0.1)', padding: '6px 12px', borderRadius: '20px' }}>
                      POS: {telemetry.x.toFixed(2)}, {telemetry.y.toFixed(2)}
                    </div>
                  </div>
                  
                  <div style={{ flex: 1, background: '#020617', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden', boxShadow: 'inset 0 0 30px rgba(0,0,0,0.8)' }}>
                    {/* Futuristic map grid */}
                    <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(37, 99, 235, 0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(37, 99, 235, 0.15) 1px, transparent 1px)', backgroundSize: '30px 30px', backgroundPosition: 'center center' }}></div>
                    
                    {/* Dynamic Robot Blip */}
                    <motion.div 
                      animate={{ top: mapY, left: mapX }}
                      transition={{ type: "spring", stiffness: 100, damping: 20 }}
                      style={{ 
                        width: '16px', height: '16px', background: 'var(--accent-cyan)', borderRadius: '50%', 
                        position: 'absolute', 
                        transform: 'translate(-50%, -50%)', boxShadow: '0 0 20px var(--accent-cyan)'
                      }}
                    >
                      <div style={{ position: 'absolute', inset: '-12px', borderRadius: '50%', border: '2px solid var(--accent-cyan)', animation: 'pulse-glow 2s cubic-bezier(0, 0, 0.2, 1) infinite' }}></div>
                    </motion.div>
                  </div>
                </GlassPanel>

                <GlassPanel style={{ minHeight: '450px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ marginBottom: '1.5rem', margin: 0 }}>System Operations Log</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', flex: 1, paddingRight: '8px' }}>
                    <AnimatePresence>
                      {logs.length === 0 ? (
                        <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '2rem', fontStyle: 'italic' }}>Listening for telemetry events...</div>
                      ) : (
                        logs.map((log, i) => (
                          <motion.div 
                            key={i + log.time + log.event}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.3 }}
                            style={{ 
                              padding: '14px', 
                              background: 'rgba(0,0,0,0.3)', 
                              borderRadius: '10px', 
                              display: 'flex', 
                              gap: '12px', 
                              borderLeft: `4px solid var(--accent-${log.type === 'success' ? 'green' : log.type === 'warning' ? 'red' : 'blue'})`,
                              boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                            }}
                          >
                            <span className="mono" style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>[{log.time}]</span>
                            <span style={{ fontSize: '0.95rem', color: log.type === 'warning' ? 'var(--accent-red)' : '#fff' }}>{log.event}</span>
                          </motion.div>
                        ))
                      )}
                    </AnimatePresence>
                  </div>
                </GlassPanel>
              </div>
            </motion.div>
          )}

          {activeTab === 'inventory' && (
            <motion.div key="inventory" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
              <GlassPanel style={{ minHeight: '600px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Package size={28} color="var(--accent-cyan)" />
                    <div>
                      <h3 style={{ margin: 0, fontSize: '1.5rem' }}>Inventory Database</h3>
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Manage robotics components and stored items.</span>
                    </div>
                  </div>
                  <button onClick={openAddInventoryModal} className="btn" style={{ background: 'var(--accent-blue)', color: '#fff', border: 'none', boxShadow: '0 0 15px var(--accent-blue-glow)' }}>
                    + Add New Equipment
                  </button>
                </div>

                <div style={{ overflowX: 'auto', flex: 1 }}>
                  {inventoryItems.length === 0 ? (
                    <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '4rem' }}>
                      <Package size={48} style={{ opacity: 0.2, marginBottom: '1rem' }} />
                      <p>No inventory items found. Add one to get started.</p>
                    </div>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-secondary)' }}>
                          <th style={{ padding: '12px', fontWeight: 500 }}>ID</th>
                          <th style={{ padding: '12px', fontWeight: 500 }}>Equipment Name</th>
                          <th style={{ padding: '12px', fontWeight: 500 }}>Product Details</th>
                          <th style={{ padding: '12px', fontWeight: 500 }}>Qty</th>
                          <th style={{ padding: '12px', fontWeight: 500 }}>Rack</th>
                          <th style={{ padding: '12px', fontWeight: 500 }}>Status</th>
                          <th style={{ padding: '12px', fontWeight: 500, textAlign: 'right' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {inventoryItems.map(item => (
                          <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.2s' }} className="hover-row">
                            <td style={{ padding: '16px 12px' }} className="mono">{item.id}</td>
                            <td style={{ padding: '16px 12px', fontWeight: 600, color: '#fff' }}>{item.name}</td>
                            <td style={{ padding: '16px 12px', color: 'var(--text-secondary)', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.description || '-'}</td>
                            <td style={{ padding: '16px 12px' }} className="mono">{item.quantity}</td>
                            <td style={{ padding: '16px 12px' }} className="mono">{item.rack_id || 'Unassigned'}</td>
                            <td style={{ padding: '16px 12px' }}>
                              <span style={{ 
                                padding: '4px 10px', 
                                borderRadius: '12px', 
                                fontSize: '0.8rem',
                                background: item.available ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
                                color: item.available ? 'var(--accent-green)' : 'var(--accent-red)',
                                border: `1px solid ${item.available ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`
                              }}>
                                {item.available ? 'Available' : 'Out of Stock'}
                              </span>
                            </td>
                            <td style={{ padding: '16px 12px', textAlign: 'right', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                              <button onClick={() => openEditInventoryModal(item)} className="btn" style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', background: 'rgba(255,255,255,0.05)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}>
                                <Edit2 size={14} /> Edit
                              </button>
                              <button onClick={() => handleInventoryDelete(item.id, item.name)} className="btn" style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', background: 'rgba(244, 63, 94, 0.1)', color: 'var(--accent-red)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
                                <Trash2 size={14} /> Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </GlassPanel>
            </motion.div>
          )}

          {activeTab === 'system' && (
            <motion.div key="system" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
              <GlassPanel style={{ minHeight: '600px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '2rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: '1.5rem' }}>
                  <Settings size={28} color="var(--accent-blue)" />
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.5rem' }}>Global Configuration</h3>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Real-time synchronized parameters. Changes reflect instantly across all operational nodes.</span>
                  </div>
                </div>
                
                <div className="grid-cols-2" style={{ gap: '32px' }}>
                  {/* Safe Mode Toggle */}
                  <GlassPanel className="hover-scale" style={{ padding: '24px', background: 'rgba(0,0,0,0.2)' }}>
                    <div className="flex-between" style={{ marginBottom: '16px' }}>
                      <div>
                        <h4 style={{ fontSize: '1.2rem', marginBottom: '8px', color: config.safe_mode ? 'var(--accent-green)' : '#fff' }}>Operational Safe Mode</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>Restricts maximum velocity and rigorously enforces hardware collision avoidance algorithms.</p>
                      </div>
                      <div className="switch-container" onClick={() => handleConfigChange('safe_mode', !config.safe_mode)}>
                        <div className="switch" data-active={config.safe_mode} style={{ background: config.safe_mode ? 'var(--accent-green)' : '' }}>
                          <div className="switch-handle"></div>
                        </div>
                      </div>
                    </div>
                  </GlassPanel>

                  {/* Maintenance Mode Toggle */}
                  <GlassPanel className="hover-scale" style={{ padding: '24px', background: config.maintenance_mode ? 'rgba(244, 63, 94, 0.05)' : 'rgba(0,0,0,0.2)', border: config.maintenance_mode ? '1px solid rgba(244, 63, 94, 0.3)' : '' }}>
                    <div className="flex-between" style={{ marginBottom: '16px' }}>
                      <div>
                        <h4 style={{ fontSize: '1.2rem', marginBottom: '8px', color: config.maintenance_mode ? 'var(--accent-red)' : '#fff' }}>Maintenance Override</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>Suspends all autonomous routines and scheduled deliveries for manual hardware servicing.</p>
                      </div>
                      <div className="switch-container" onClick={() => handleConfigChange('maintenance_mode', !config.maintenance_mode)}>
                        <div className="switch" data-active={config.maintenance_mode} style={{ background: config.maintenance_mode ? 'var(--accent-red)' : '' }}>
                          <div className="switch-handle"></div>
                        </div>
                      </div>
                    </div>
                  </GlassPanel>

                  {/* Max Speed Slider */}
                  <GlassPanel className="hover-scale" style={{ padding: '24px', background: 'rgba(0,0,0,0.2)' }}>
                    <div className="flex-between" style={{ marginBottom: '16px' }}>
                      <h4 style={{ fontSize: '1.2rem', margin: 0 }}>Maximum Velocity Cap</h4>
                      <span className="mono" style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>{config.max_speed} m/s</span>
                    </div>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '24px' }}>Limits the top traversal speed of the robotic unit during standard operations.</p>
                    <input 
                      type="range" 
                      className="slider" 
                      min="0.1" max="5.0" step="0.1" 
                      value={config.max_speed} 
                      onChange={(e) => handleConfigChange('max_speed', parseFloat(e.target.value))} 
                    />
                    <div className="flex-between" style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span>0.1 m/s (Crawl)</span>
                      <span>5.0 m/s (Max)</span>
                    </div>
                  </GlassPanel>

                  {/* Telemetry Frequency Slider */}
                  <GlassPanel className="hover-scale" style={{ padding: '24px', background: 'rgba(0,0,0,0.2)' }}>
                    <div className="flex-between" style={{ marginBottom: '16px' }}>
                      <h4 style={{ fontSize: '1.2rem', margin: 0 }}>Telemetry Polling Rate</h4>
                      <span className="mono" style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-blue)' }}>{config.telemetry_frequency} ms</span>
                    </div>
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '24px' }}>Determines the frequency at which telemetry packets are broadcasted to connected clients.</p>
                    <input 
                      type="range" 
                      className="slider" 
                      min="100" max="5000" step="100" 
                      value={config.telemetry_frequency} 
                      onChange={(e) => handleConfigChange('telemetry_frequency', parseInt(e.target.value))} 
                    />
                    <div className="flex-between" style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span>100 ms (High Cost)</span>
                      <span>5000 ms (Eco)</span>
                    </div>
                  </GlassPanel>
                </div>
              </GlassPanel>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Inventory Modal */}
      <AnimatePresence>
        {isInventoryModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(5px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.2 }} style={{ width: '100%', maxWidth: '500px' }}>
              <GlassPanel style={{ border: '1px solid var(--accent-blue)', boxShadow: '0 0 30px rgba(37, 99, 235, 0.2)' }}>
                <h3 style={{ marginTop: 0, marginBottom: '1.5rem', fontSize: '1.5rem' }}>{editingItem ? 'Edit Equipment' : 'Add New Equipment'}</h3>
                <form onSubmit={handleInventorySubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Equipment Name *</label>
                    <input required type="text" className="input" value={inventoryFormData.name} onChange={e => setInventoryFormData({...inventoryFormData, name: e.target.value})} placeholder="e.g., Titanium Sensor" />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Product Details / Info</label>
                    <textarea className="input" value={inventoryFormData.description} onChange={e => setInventoryFormData({...inventoryFormData, description: e.target.value})} placeholder="Item specifications and equipment info..." rows={3} style={{ resize: 'vertical' }} />
                  </div>
                  <div style={{ display: 'flex', gap: '16px' }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Quantity *</label>
                      <input required type="number" min="0" className="input" value={inventoryFormData.quantity} onChange={e => setInventoryFormData({...inventoryFormData, quantity: parseInt(e.target.value)})} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Assigned Rack ID</label>
                      <input type="number" className="input" value={inventoryFormData.rack_id} onChange={e => setInventoryFormData({...inventoryFormData, rack_id: e.target.value})} placeholder="Optional" />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '1rem' }}>
                    <button type="button" onClick={() => setIsInventoryModalOpen(false)} className="btn" style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', color: '#fff' }}>Cancel</button>
                    <button type="submit" className="btn" style={{ background: 'var(--accent-blue)', color: '#fff', border: 'none', boxShadow: '0 0 15px var(--accent-blue-glow)' }}>{editingItem ? 'Save Changes' : 'Add Equipment'}</button>
                  </div>
                </form>
              </GlassPanel>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
