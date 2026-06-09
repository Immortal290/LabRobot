import React, { useState, useEffect, useRef } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { Battery, Cpu, Map as MapIcon, Package, LogOut, Navigation, Settings } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const AdminDashboard: React.FC = () => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [telemetry, setTelemetry] = useState({ battery: 100, cpu_temp: 40, x: 0, y: 0, status: 'Idle', mission: 'Standby', rack_status: ["locked", "locked", "locked", "locked"] });
  const [logs, setLogs] = useState<{ time: string, event: string, type: 'info' | 'success' | 'warning' }[]>([]);
  const [activeTab, setActiveTab] = useState('live_map');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
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
            rack_status: data.rack_status
          });
          if (data.log) {
            const logType: 'info' | 'success' | 'warning' = data.log.includes('warning') ? 'warning' : data.log.includes('Obstacle') ? 'warning' : data.log.includes('confirmed') ? 'success' : 'info';
            const newLog = {
              time: data.timestamp,
              event: data.log,
              type: logType
            };
            setLogs(prev => [newLog, ...prev].slice(0, 10)); // Keep last 10 logs
          }
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

  // Convert X/Y to percentage for map display. Assuming arena is roughly -5 to +5 meters.
  const mapX = `${50 + (telemetry.x / 5) * 50}%`;
  const mapY = `${50 - (telemetry.y / 5) * 50}%`;

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <div className="sidebar glass-panel" style={{ borderRadius: 0, borderTop: 0, borderBottom: 0, borderLeft: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '2rem' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--accent-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
            {user?.username.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{user?.username}</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{user?.role}</span>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button 
            className="btn" 
            style={{ background: activeTab === 'live_map' ? 'rgba(59,130,246,0.1)' : 'transparent', color: activeTab === 'live_map' ? 'var(--accent-blue)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '12px' }}
            onClick={() => setActiveTab('live_map')}
          >
            <MapIcon size={20} />
            <span>Live Map</span>
          </button>
          <button 
            className="btn" 
            style={{ background: activeTab === 'inventory' ? 'rgba(59,130,246,0.1)' : 'transparent', color: activeTab === 'inventory' ? 'var(--accent-blue)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '12px' }}
            onClick={() => setActiveTab('inventory')}
          >
            <Package size={20} />
            <span>Inventory</span>
          </button>
          <button 
            className="btn" 
            style={{ background: activeTab === 'deliveries' ? 'rgba(59,130,246,0.1)' : 'transparent', color: activeTab === 'deliveries' ? 'var(--accent-blue)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '12px' }}
            onClick={() => setActiveTab('deliveries')}
          >
            <Navigation size={20} />
            <span>Deliveries</span>
          </button>
          <button 
            className="btn" 
            style={{ background: activeTab === 'system' ? 'rgba(59,130,246,0.1)' : 'transparent', color: activeTab === 'system' ? 'var(--accent-blue)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', textAlign: 'left', padding: '12px' }}
            onClick={() => setActiveTab('system')}
          >
            <Settings size={20} />
            <span>System</span>
          </button>
        </nav>

        <div style={{ marginTop: 'auto' }}>
          <button onClick={handleLogout} className="btn" style={{ width: '100%', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center' }}>
            <LogOut size={20} />
            <span>Logout</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h2>Robot Telemetry & Control</h2>
          <div style={{ display: 'flex', gap: '16px' }}>
            <div className="flex-center" style={{ gap: '8px', background: 'rgba(16, 185, 129, 0.1)', padding: '8px 16px', borderRadius: '20px', color: 'var(--accent-green)' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-green)', boxShadow: '0 0 10px var(--accent-green)', animation: 'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite' }}></div>
              System Online
            </div>
          </div>
        </header>

        {activeTab === 'live_map' && (
          <>
            <div className="grid-cols-4" style={{ marginBottom: '2rem' }}>
          <GlassPanel>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
              <div style={{ background: 'rgba(6, 182, 212, 0.2)', padding: '12px', borderRadius: '12px', color: 'var(--accent-cyan)' }}>
                <Battery size={24} />
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Battery Level</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{telemetry.battery}%</div>
              </div>
            </div>
            <div style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${telemetry.battery}%`, background: getBatteryColor(telemetry.battery), transition: 'width 0.5s ease-out, background 0.5s ease-out' }}></div>
            </div>
          </GlassPanel>

          <GlassPanel>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
              <div style={{ background: 'rgba(239, 68, 68, 0.2)', padding: '12px', borderRadius: '12px', color: 'var(--accent-red)' }}>
                <Cpu size={24} />
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>CPU Temp</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{telemetry.cpu_temp}°C</div>
              </div>
            </div>
             <div style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(100, (telemetry.cpu_temp / 80) * 100)}%`, background: telemetry.cpu_temp > 70 ? 'var(--accent-red)' : 'var(--accent-blue)', transition: 'width 0.5s ease-out, background 0.5s ease-out' }}></div>
            </div>
          </GlassPanel>

          <GlassPanel>
             <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ background: 'rgba(59, 130, 246, 0.2)', padding: '12px', borderRadius: '12px', color: 'var(--accent-blue)' }}>
                <Navigation size={24} />
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{telemetry.status}</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{telemetry.mission}</div>
              </div>
            </div>
          </GlassPanel>

          <GlassPanel>
             <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.2)', padding: '12px', borderRadius: '12px', color: 'var(--accent-green)' }}>
                <Package size={24} />
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Active Racks</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{telemetry.rack_status.filter(s => s === 'unlocked').length} / 4</div>
              </div>
            </div>
          </GlassPanel>
        </div>

        <div className="grid-cols-2">
          <GlassPanel style={{ minHeight: '400px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3>Live Map (ROS2 Nav2)</h3>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Pos: ({telemetry.x}, {telemetry.y})</div>
            </div>
            
            <div style={{ flex: 1, background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
              {/* Futuristic map grid */}
              <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
              
              {/* Dynamic Robot Blip */}
              <div style={{ 
                width: '12px', height: '12px', background: 'var(--accent-cyan)', borderRadius: '50%', 
                position: 'absolute', top: mapY, left: mapX, 
                transform: 'translate(-50%, -50%)', boxShadow: '0 0 15px var(--accent-cyan)',
                transition: 'top 0.5s linear, left 0.5s linear'
              }}>
                <div style={{ position: 'absolute', inset: '-10px', borderRadius: '50%', border: '1px solid var(--accent-cyan)', animation: 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite' }}></div>
              </div>
            </div>
          </GlassPanel>

          <GlassPanel style={{ minHeight: '400px', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ marginBottom: '1rem' }}>Live System Logs</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', flex: 1 }}>
              {logs.length === 0 ? (
                <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '2rem' }}>Waiting for system events...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} style={{ padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', display: 'flex', gap: '12px', borderLeft: `3px solid var(--accent-${log.type === 'success' ? 'green' : log.type === 'warning' ? 'cyan' : 'blue'})`, animation: 'fade-in 0.5s ease-out' }}>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>[{log.time}]</span>
                    <span style={{ fontSize: '0.9rem' }}>{log.event}</span>
                  </div>
                ))
              )}
            </div>
          </GlassPanel>
          </div>
          </>
        )}

        {activeTab === 'inventory' && (
          <GlassPanel style={{ minHeight: '400px' }}>
            <h3 style={{ marginBottom: '1rem' }}>Inventory Management</h3>
            <div style={{ color: 'var(--text-secondary)' }}>Inventory tracking view goes here...</div>
          </GlassPanel>
        )}

        {activeTab === 'deliveries' && (
          <GlassPanel style={{ minHeight: '400px' }}>
            <h3 style={{ marginBottom: '1rem' }}>Active Deliveries</h3>
            <div style={{ color: 'var(--text-secondary)' }}>Delivery scheduling view goes here...</div>
          </GlassPanel>
        )}

        {activeTab === 'system' && (
          <GlassPanel style={{ minHeight: '400px' }}>
            <h3 style={{ marginBottom: '1rem' }}>System Settings</h3>
            <div style={{ color: 'var(--text-secondary)' }}>System configuration view goes here...</div>
          </GlassPanel>
        )}
      </div>
    </div>
  );
};
