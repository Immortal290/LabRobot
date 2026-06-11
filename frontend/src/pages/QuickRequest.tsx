import React, { useState, useEffect, useRef } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { Smartphone, Monitor, MapPin, Package, Cpu, Battery, Send, ShieldAlert, CheckCircle, Clock, Lock, Unlock, RefreshCw, User, LogOut, Compass, Eye } from 'lucide-react';
import { inventoryApi, deliveriesApi, rackApi } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';

export const QuickRequest: React.FC = () => {
  const [username, setUsername] = useState(localStorage.getItem('quick_username') || '');
  const [tempUsername, setTempUsername] = useState('');
  const [pcNo, setPcNo] = useState('');
  const [itemId, setItemId] = useState('');
  const [location, setLocation] = useState('');
  const [inventory, setInventory] = useState<any[]>([]);
  const [recentDeliveries, setRecentDeliveries] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [activeDelivery, setActiveDelivery] = useState<any>(null);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Robot Telemetry State
  const [robotState, setRobotState] = useState({
    battery: 100,
    cpu_temp: 40,
    status: 'Idle',
    mission: 'Standby',
    x: 0,
    y: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);

  const loadInventory = () => {
    inventoryApi.getInventory()
      .then(data => setInventory(data.filter((item: any) => item.available && item.quantity > 0)))
      .catch(err => console.error('Failed to load inventory', err));
  };

  const loadRecentDeliveries = (user: string) => {
    if (!user) return;
    deliveriesApi.getQuickDeliveries(user)
      .then(data => {
        setRecentDeliveries(data);
        // Auto-select pending or in-progress deliveries if we don't have one selected
        const currentActive = data.find((d: any) => d.status === 'pending' || d.status === 'in_progress');
        if (currentActive) {
          setActiveDelivery(currentActive);
        }
      })
      .catch(err => console.error('Failed to load recent deliveries', err));
  };

  useEffect(() => {
    loadInventory();
    if (username) {
      loadRecentDeliveries(username);
    }

    // Connect to WebSocket for real-time telemetry and delivery updates
    const ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/ui`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'telemetry') {
          setRobotState({
            battery: data.battery,
            cpu_temp: data.cpu_temp,
            status: data.status,
            mission: data.mission,
            x: data.x,
            y: data.y,
          });
        } else if (data.type === 'delivery_update') {
          // Refresh list on WebSocket updates
          if (username) {
            loadRecentDeliveries(username);
          }
          // Update details of currently tracked delivery
          setActiveDelivery((current: any) => {
            if (current && data.delivery.id === current.id) {
              return data.delivery;
            }
            return current;
          });
        }
      } catch (err) {
        console.error('WS parsing error:', err);
      }
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [username]);

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (tempUsername.trim()) {
      const formatted = tempUsername.trim().toLowerCase();
      localStorage.setItem('quick_username', formatted);
      setUsername(formatted);
      loadRecentDeliveries(formatted);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('quick_username');
    setUsername('');
    setActiveDelivery(null);
    setRecentDeliveries([]);
    setMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !pcNo || !itemId || !location) {
      setMessage({ text: 'Please fill in all fields.', type: 'error' });
      return;
    }
    
    setLoading(true);
    setMessage(null);

    try {
      const selectedItem = inventory.find(i => i.id === parseInt(itemId));
      const res = await deliveriesApi.requestQuickItem({
        username,
        pc_no: pcNo,
        item_id: parseInt(itemId),
        location,
        rack_id: selectedItem?.rack_id || null
      });
      setActiveDelivery(res);
      setMessage({ text: 'Robot dispatched successfully!', type: 'success' });
      loadInventory();
      loadRecentDeliveries(username);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to dispatch robot.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleUnlockRack = async () => {
    if (!activeDelivery || !activeDelivery.rack_id) return;
    try {
      await rackApi.unlockRack(activeDelivery.rack_id);
      setMessage({ text: `Cabinet Rack ${activeDelivery.rack_id} unlocked successfully!`, type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to unlock rack.', type: 'error' });
    }
  };

  const getStatusStep = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending': return 1;
      case 'in_progress': return 2;
      case 'completed': return 3;
      default: return 0;
    }
  };

  // Mapping coordinates: robot x, y are usually between -5.0 and 5.0
  const mapX = `${50 + (robotState.x / 5) * 50}%`;
  const mapY = `${50 - (robotState.y / 5) * 50}%`;

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed') return 'var(--accent-green)';
    if (s === 'in_progress') return 'var(--accent-blue)';
    if (s === 'pending') return '#f59e0b';
    return 'var(--accent-red)';
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', padding: '16px', maxWidth: '480px', margin: '0 auto', gap: '20px' }}>
      
      {/* Header Bar */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 12px var(--accent-blue-glow)' }}>
            <Smartphone size={18} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.2rem', margin: 0, fontWeight: 700, letterSpacing: '-0.5px' }}>LabRobot</h1>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', display: 'block', marginTop: '-2px', fontWeight: 600 }}>Mobile Request Portal</span>
          </div>
        </div>
        
        {username && (
          <button onClick={handleLogout} className="btn" style={{ padding: '6px 10px', background: 'rgba(244, 63, 94, 0.1)', color: 'var(--accent-red)', border: '1px solid rgba(244, 63, 94, 0.2)', borderRadius: '10px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <LogOut size={14} /> {username}
          </button>
        )}
      </header>

      <AnimatePresence mode="wait">
        {!username ? (
          /* Portal Access Login Form */
          <motion.div
            key="login-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <GlassPanel style={{ padding: '32px 24px', borderRadius: '24px', textAlign: 'center', border: '1px solid var(--glass-border)' }}>
              <div style={{ width: '56px', height: '56px', borderRadius: '18px', background: 'rgba(6, 182, 212, 0.1)', border: '1px solid var(--accent-cyan-glow)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px auto' }}>
                <User size={28} color="var(--accent-cyan)" />
              </div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>Student Sign-In</h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '24px', lineHeight: 1.5 }}>
                Enter your Username or ID to connect to the automated request portal and monitor delivery tracks.
              </p>

              <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ position: 'relative' }}>
                  <input
                    required
                    type="text"
                    className="input-field"
                    placeholder="Enter Student Username"
                    value={tempUsername}
                    onChange={e => setTempUsername(e.target.value)}
                    style={{ paddingLeft: '44px', textAlign: 'center' }}
                  />
                  <User size={16} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                </div>
                <button type="submit" className="btn btn-primary" style={{ padding: '14px', borderRadius: '12px', width: '100%', fontSize: '0.95rem' }}>
                  Connect Portal
                </button>
              </form>
            </GlassPanel>
          </motion.div>
        ) : (
          /* Main Dashboard Content */
          <motion.div
            key="dashboard-view"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.25 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
          >
            {/* Realtime Live Telemetry Map Panel */}
            <GlassPanel style={{ padding: '20px', borderRadius: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Compass size={18} color="var(--accent-cyan)" />
                  <h3 style={{ fontSize: '1.05rem', margin: 0 }}>Live Radar Telemetry</h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ 
                    width: '8px', height: '8px', borderRadius: '50%', 
                    background: robotState.status === 'Offline' ? 'var(--accent-red)' : 'var(--accent-green)',
                    animation: robotState.status === 'Offline' ? 'none' : 'pulse-glow 2s infinite' 
                  }} />
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{robotState.status}</span>
                </div>
              </div>

              {/* Dynamic Coordinate Map */}
              <div style={{ 
                height: '140px', background: 'rgba(0,0,0,0.4)', borderRadius: '16px', border: '1px solid var(--glass-border)', 
                position: 'relative', overflow: 'hidden', marginBottom: '14px',
                backgroundImage: 'radial-gradient(var(--glass-border) 1px, transparent 1px)',
                backgroundSize: '20px 20px'
              }}>
                {/* SVG coordinate axes */}
                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                  <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '1px', background: 'rgba(255,255,255,0.04)' }} />
                  <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: '1px', background: 'rgba(255,255,255,0.04)' }} />
                </div>

                {/* Radar Grid Circles */}
                <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate( -50%, -50% )', width: '80px', height: '80px', borderRadius: '50%', border: '1px dashed rgba(6, 182, 212, 0.08)' }} />
                <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate( -50%, -50% )', width: '120px', height: '120px', borderRadius: '50%', border: '1px dashed rgba(6, 182, 212, 0.04)' }} />

                {/* Pulsing Robot Indicator */}
                <motion.div 
                  style={{ 
                    position: 'absolute', 
                    left: mapX, 
                    top: mapY, 
                    width: '14px', 
                    height: '14px', 
                    borderRadius: '50%', 
                    background: 'var(--accent-cyan)', 
                    transform: 'translate(-50%, -50%)',
                    boxShadow: '0 0 15px var(--accent-cyan)' 
                  }}
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                />
                
                {/* Positional Label Overlay */}
                <div style={{ position: 'absolute', bottom: '8px', left: '12px', fontSize: '0.75rem', color: 'var(--accent-cyan)' }} className="mono">
                  RADAR: ({robotState.x.toFixed(2)}, {robotState.y.toFixed(2)})
                </div>
                
                <div style={{ position: 'absolute', bottom: '8px', right: '12px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Mission: <span style={{ color: '#fff', fontWeight: 600 }}>{robotState.mission}</span>
                </div>
              </div>

              {/* Status details bar */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', fontSize: '0.8rem', textAlign: 'center' }}>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>Battery</div>
                  <div style={{ fontWeight: 700, color: 'var(--accent-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    <Battery size={12} /> {robotState.battery}%
                  </div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>CPU Temp</div>
                  <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    <Cpu size={12} /> {robotState.cpu_temp}°C
                  </div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>Robot Queue</div>
                  <div style={{ fontWeight: 700, color: 'var(--accent-purple)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    <Clock size={12} /> {robotState.status === 'Idle' ? 'No Delay' : 'Busy'}
                  </div>
                </div>
              </div>
            </GlassPanel>

            <AnimatePresence mode="wait">
              {/* If tracked delivery is selected, show details. Otherwise, show form. */}
              {activeDelivery ? (
                <motion.div
                  key="active-delivery"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.2 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
                >
                  {/* Delivery tracker */}
                  <GlassPanel style={{ padding: '24px', borderRadius: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                      <h3 style={{ fontSize: '1.1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Compass size={18} color="var(--accent-blue)" /> Track Delivery
                      </h3>
                      <button onClick={() => setActiveDelivery(null)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-cyan)', fontSize: '0.8rem', cursor: 'pointer', fontWeight: 600 }}>
                        New Dispatch
                      </button>
                    </div>

                    {/* Step Visualizer */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative', paddingLeft: '32px', marginBottom: '24px' }}>
                      {/* Vertical connector line */}
                      <div style={{ position: 'absolute', left: '9px', top: '10px', bottom: '10px', width: '2px', background: 'rgba(255,255,255,0.06)' }} />
                      
                      {/* Step 1 */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ 
                          position: 'absolute', left: '-31px', top: '2px', width: '18px', height: '18px', borderRadius: '50%', 
                          background: getStatusStep(activeDelivery.status) >= 1 ? 'var(--accent-green)' : 'rgba(255,255,255,0.1)',
                          boxShadow: getStatusStep(activeDelivery.status) >= 1 ? '0 0 10px var(--accent-green)' : 'none',
                          display: 'flex', alignItems: 'center', justifyContent: 'center' 
                        }}>
                          {getStatusStep(activeDelivery.status) >= 1 && <CheckCircle size={10} color="#fff" />}
                        </div>
                        <div style={{ fontWeight: 600, color: getStatusStep(activeDelivery.status) >= 1 ? '#fff' : 'var(--text-secondary)', fontSize: '0.9rem' }}>Request Registered</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Delivery queued on server</div>
                      </div>

                      {/* Step 2 */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ 
                          position: 'absolute', left: '-31px', top: '2px', width: '18px', height: '18px', borderRadius: '50%', 
                          background: getStatusStep(activeDelivery.status) >= 2 ? 'var(--accent-blue)' : 'rgba(255,255,255,0.1)',
                          boxShadow: getStatusStep(activeDelivery.status) >= 2 ? '0 0 10px var(--accent-blue)' : 'none',
                          display: 'flex', alignItems: 'center', justifyContent: 'center' 
                        }}>
                          {getStatusStep(activeDelivery.status) >= 2 && <CheckCircle size={10} color="#fff" />}
                        </div>
                        <div style={{ fontWeight: 600, color: getStatusStep(activeDelivery.status) >= 2 ? '#fff' : 'var(--text-secondary)', fontSize: '0.9rem' }}>Robot Dispatched</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {activeDelivery.rack_id ? `Retrieving from Rack Compartment ${activeDelivery.rack_id}` : 'In traversal'}
                        </div>
                      </div>

                      {/* Step 3 */}
                      <div style={{ position: 'relative' }}>
                        <div style={{ 
                          position: 'absolute', left: '-31px', top: '2px', width: '18px', height: '18px', borderRadius: '50%', 
                          background: getStatusStep(activeDelivery.status) >= 3 ? 'var(--accent-green)' : 'rgba(255,255,255,0.1)',
                          boxShadow: getStatusStep(activeDelivery.status) >= 3 ? '0 0 10px var(--accent-green)' : 'none',
                          display: 'flex', alignItems: 'center', justifyContent: 'center' 
                        }}>
                          {getStatusStep(activeDelivery.status) >= 3 && <CheckCircle size={10} color="#fff" />}
                        </div>
                        <div style={{ fontWeight: 600, color: getStatusStep(activeDelivery.status) >= 3 ? '#fff' : 'var(--text-secondary)', fontSize: '0.9rem' }}>Arrived at Workbench</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Robot reached destination {activeDelivery.destination}</div>
                      </div>
                    </div>

                    {/* Metadata Specs Table */}
                    <div style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', borderRadius: '16px', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Tracking code:</span>
                        <span className="mono" style={{ fontWeight: 600 }}>#DEL-{activeDelivery.id}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Equipment requested:</span>
                        <span style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{activeDelivery.item_name || `Item ID: ${activeDelivery.item_id}`}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>PC Node / Bench:</span>
                        <span style={{ fontWeight: 600 }}>{activeDelivery.pc_no} ({activeDelivery.location})</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Request Status:</span>
                        <span style={{ fontWeight: 700, color: getStatusColor(activeDelivery.status) }}>{activeDelivery.status.toUpperCase()}</span>
                      </div>
                    </div>
                  </GlassPanel>

                  {/* Cabinet Controller Panel */}
                  {activeDelivery.rack_id && (
                    <GlassPanel style={{ padding: '20px', borderRadius: '24px', border: '1px solid var(--accent-purple-glow)', boxShadow: '0 0 20px rgba(139, 92, 246, 0.15)' }}>
                      <h4 style={{ fontSize: '1rem', margin: '0 0 8px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Lock size={16} color="var(--accent-purple)" /> Cabinet Lock Manager
                      </h4>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.4 }}>
                        When the robot arrives at your workbench location, tap the button below to unlock the secure cabinet compartment.
                      </p>

                      <div style={{ display: 'flex', gap: '12px' }}>
                        <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '10px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Rack Slot</span>
                          <span className="mono" style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>R-{activeDelivery.rack_id}</span>
                        </div>
                        <button 
                          onClick={handleUnlockRack}
                          disabled={activeDelivery.status !== 'completed' && activeDelivery.status !== 'in_progress'}
                          className="btn"
                          style={{ 
                            flex: 1.5,
                            background: 'linear-gradient(135deg, var(--accent-purple), #7c3aed)',
                            color: '#fff', 
                            border: 'none', 
                            boxShadow: '0 4px 15px var(--accent-purple-glow)',
                            opacity: (activeDelivery.status === 'completed' || activeDelivery.status === 'in_progress') ? 1 : 0.4,
                            cursor: (activeDelivery.status === 'completed' || activeDelivery.status === 'in_progress') ? 'pointer' : 'not-allowed'
                          }}
                        >
                          <Unlock size={16} /> Unlock Cabinet
                        </button>
                      </div>
                    </GlassPanel>
                  )}
                </motion.div>
              ) : (
                /* Submission Dispatch Request Form */
                <motion.div
                  key="dispatch-form"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.2 }}
                >
                  <GlassPanel style={{ padding: '24px', borderRadius: '24px' }}>
                    <h3 style={{ fontSize: '1.2rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Send size={18} color="var(--accent-cyan)" /> Dispatch Equipment
                    </h3>

                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '12px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Target PC *</label>
                          <div style={{ position: 'relative' }}>
                            <input 
                              required
                              type="text" 
                              className="input-field" 
                              value={pcNo}
                              onChange={e => setPcNo(e.target.value)}
                              placeholder="e.g. PC-14"
                              style={{ paddingLeft: '40px' }}
                            />
                            <Monitor size={14} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                          </div>
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Location/Bench *</label>
                          <div style={{ position: 'relative' }}>
                            <input 
                              required
                              type="text" 
                              className="input-field" 
                              value={location}
                              onChange={e => setLocation(e.target.value)}
                              placeholder="e.g. Row B-4"
                              style={{ paddingLeft: '40px' }}
                            />
                            <MapPin size={14} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                          </div>
                        </div>
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Select Equipment Item *</label>
                        <div style={{ position: 'relative' }}>
                          <select
                            required
                            className="input-field"
                            value={itemId}
                            onChange={e => setItemId(e.target.value)}
                            style={{ paddingLeft: '40px', appearance: 'none' }}
                          >
                            <option value="">-- Choose Item --</option>
                            {inventory.map(item => (
                              <option key={item.id} value={item.id}>
                                {item.name} ({item.quantity} in stock)
                              </option>
                            ))}
                          </select>
                          <Package size={14} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        </div>
                      </div>

                      {message && (
                        <div style={{ 
                          padding: '12px', 
                          borderRadius: '10px', 
                          fontSize: '0.8rem', 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: '8px', 
                          background: message.type === 'error' ? 'rgba(244, 63, 94, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                          color: message.type === 'error' ? 'var(--accent-red)' : 'var(--accent-green)',
                          border: `1px solid ${message.type === 'error' ? 'rgba(244, 63, 94, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`
                        }}>
                          <ShieldAlert size={14} />
                          <span>{message.text}</span>
                        </div>
                      )}

                      <button 
                        type="submit" 
                        disabled={loading}
                        className="btn btn-primary" 
                        style={{ width: '100%', padding: '14px', borderRadius: '12px', fontSize: '0.95rem', marginTop: '4px' }}
                      >
                        {loading ? (
                          <>
                            <RefreshCw size={16} className="spinner" /> Dispatched...
                          </>
                        ) : (
                          <>
                            <Send size={16} /> Request Robot Delivery
                          </>
                        )}
                      </button>
                    </form>
                  </GlassPanel>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Recent Requests Log Card */}
            {recentDeliveries.length > 0 && (
              <GlassPanel style={{ padding: '20px', borderRadius: '24px' }}>
                <h3 style={{ fontSize: '1rem', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Clock size={16} color="var(--accent-blue)" /> Your Requests
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '160px', overflowY: 'auto' }}>
                  {recentDeliveries.map((delivery) => (
                    <div 
                      key={delivery.id} 
                      style={{ 
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                        padding: '10px 12px', background: activeDelivery?.id === delivery.id ? 'rgba(6, 182, 212, 0.08)' : 'rgba(0,0,0,0.15)', 
                        borderRadius: '12px', border: activeDelivery?.id === delivery.id ? '1px solid var(--accent-cyan)' : '1px solid var(--glass-border)',
                        transition: 'all 0.2s'
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600 }} className="mono">#DEL-{delivery.id}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{delivery.destination}</div>
                      </div>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ 
                          fontSize: '0.75rem', fontWeight: 600, color: getStatusColor(delivery.status),
                          background: `${getStatusColor(delivery.status)}15`,
                          padding: '2px 8px', borderRadius: '6px'
                        }}>
                          {delivery.status.toUpperCase()}
                        </span>
                        
                        {activeDelivery?.id !== delivery.id && (delivery.status === 'pending' || delivery.status === 'in_progress') && (
                          <button 
                            onClick={() => {
                              setActiveDelivery(delivery);
                              setMessage(null);
                            }}
                            className="btn" 
                            style={{ padding: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}
                          >
                            <Eye size={12} color="var(--accent-cyan)" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </GlassPanel>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
