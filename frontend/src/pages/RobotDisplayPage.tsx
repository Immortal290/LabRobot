import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RobotDisplay } from '../components/RobotDisplay';
import {
  RobotState,
  mapTelemetryToState,
  getRobotStateConfig,
} from '../lib/robotStateLibrary';
import {
  rackApi,
  configApi,
  deliveriesApi,
  usersApi,
  inventoryApi,
} from '../services/api';

export const RobotDisplayPage: React.FC = () => {
  // ─── STATE MANAGEMENT ──────────────────────────────────────────────────────
  const [currentState, setCurrentState] = useState<RobotState>(RobotState.IDLE);
  const [telemetry, setTelemetry]       = useState<any>(null);
  const [wsConnected, setWsConnected]   = useState(false);
  const [manualOverride, setManualOverride] = useState(false);
  
  // Kiosk Core Data
  const [racks, setRacks] = useState<any[]>([]);
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [inventory, setInventory] = useState<any[]>([]);
  const [localIp, setLocalIp] = useState<string>('Detecting...');
  const [tunnelUrl, setTunnelUrl] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>(['[SYSTEM] Lab Buddy Kiosk initialized.']);
  
  // Interactive Modals/Overlays
  const [eStopActive, setEStopActive] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [selectedRackId, setSelectedRackId] = useState<number | null>(null);
  const [pinCode, setPinCode] = useState('');
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState(false);
  
  // Arrival Retrieval Modal
  const [showArrivalModal, setShowArrivalModal] = useState(false);
  const [arrivedDelivery, setArrivedDelivery] = useState<any | null>(null);
  
  // Transient Toast Notification
  const [toast, setToast] = useState<{ message: string; type: 'info' | 'success' | 'warning' | 'error' } | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);

  // ─── AUTO LOGIN FOR KIOSK BYPASS ──────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      const formData = new URLSearchParams();
      formData.append('username', 'user');
      formData.append('password', 'user');
      
      fetch('/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString()
      })
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Failed to auto-login');
      })
      .then(data => {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify({ username: 'user', role: 'Student', id: 2 }));
        addLog('[AUTH] Auto-logged in kiosk user.');
        window.location.reload();
      })
      .catch(err => {
        console.error("Auto login error:", err);
        addLog('[ERROR] Kiosk auto-login failed. Please ensure backend has seeded users.');
      });
    }
  }, []);

  // ─── UTILITY: APPEND EVENT LOGS ────────────────────────────────────────────
  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev].slice(0, 30));
  };

  // ─── UTILITY: TRIGGER DYNAMIC TOASTS ───────────────────────────────────────
  const triggerToast = (message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // ─── INITIAL STATIC DATA FETCH ─────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      // Local IP & Cloudflare Tunnel
      configApi.getNetworkIp()
        .then(data => setLocalIp(data.ip || '127.0.0.1'))
        .catch(() => setLocalIp('127.0.0.1'));
      
      configApi.getTunnelUrl()
        .then(data => setTunnelUrl(data.url))
        .catch(() => setTunnelUrl(null));
      
      // Load Core DB states
      const fetchCoreData = async () => {
        try {
          const [racksData, deliveriesData, usersData, inventoryData] = await Promise.all([
            rackApi.getRacks(),
            deliveriesApi.getDeliveries(),
            usersApi.getUsers().catch(() => []),
            inventoryApi.getInventory().catch(() => [])
          ]);
          setRacks(racksData);
          setDeliveries(deliveriesData);
          setUsers(usersData);
          setInventory(inventoryData);
        } catch (err) {
          console.error("Core data fetch error:", err);
        }
      };
      
      fetchCoreData();
      const interval = setInterval(fetchCoreData, 5000); // 5s sync backup
      return () => clearInterval(interval);
    }
  }, []);

  // ─── WEBSOCKET CLIENT CONFIGURATION ────────────────────────────────────────
  const connectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/ui`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      addLog('[NET] Live WebSocket connection established.');
      triggerToast('WebSocket Connected', 'success');
    };

    ws.onclose = () => {
      setWsConnected(false);
      addLog('[NET] WebSocket connection closed. Retrying...');
      triggerToast('WebSocket Offline', 'error');
      setTimeout(connectWebSocket, 5000);
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        
        // 1. Process telemetry data
        if (data.type === 'telemetry') {
          setTelemetry(data);
          
          if (data.log) {
            addLog(`[ROS] ${data.log}`);
            triggerToast(data.log, 'info');
          }

          // Handle physical e-stop
          if (data.status?.toLowerCase().includes('emergency') || data.status?.toLowerCase().includes('estop')) {
            setEStopActive(true);
          }

          // Sync Rack locks based on telemetry state
          if (data.rack_status && Array.isArray(data.rack_status)) {
            setRacks(prev => prev.map((r, idx) => {
              if (idx < data.rack_status.length) {
                return { ...r, lock_status: data.rack_status[idx] };
              }
              return r;
            }));
          }

          // Drive screen visual face animation (unless overridden manually)
          if (!manualOverride) {
            const derived = mapTelemetryToState(data.status, data.mission, data.battery);
            setCurrentState(derived);
            
            // Check for delivery arrival retrieval popup
            if ((derived === RobotState.ARRIVED || derived === RobotState.TASK_SUCCESS) && !showArrivalModal) {
              // Find the active delivery that matches this arrival
              const active = deliveries.find(d => d.status === 'in_progress' || d.status === 'pending' || d.status === 'arrived');
              if (active) {
                setArrivedDelivery(active);
                setShowArrivalModal(true);
                addLog(`[ARRIVED] Reached destination. Awaiting item retrieval for Rack ${active.rack_id}.`);
              } else if (deliveries.length > 0) {
                // Fallback to latest delivery
                setArrivedDelivery(deliveries[0]);
                setShowArrivalModal(true);
              }
            }
          }
        }
        
        // 2. Process DB broadcast updates
        if (data.type === 'delivery_update') {
          addLog(`[DB] Delivery #${data.delivery.id} updated to '${data.delivery.status}'`);
          triggerToast(`Delivery status: ${data.delivery.status}`, 'info');
          // Reload deliveries immediately
          deliveriesApi.getDeliveries().then(setDeliveries).catch(() => {});
        }
        
        if (data.type === 'config_update') {
          addLog('[DB] System configuration update broadcast received.');
          triggerToast('System Config Updated', 'info');
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };
  };

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [deliveries]);

  // ─── INTERACTIVE ACTIONS ───────────────────────────────────────────────────
  
  // Software E-Stop Trigger
  const triggerSoftwareEStop = () => {
    setEStopActive(true);
    addLog('[ESTOP] SOFTWARE EMERGENCY STOP ACTIVATED.');
    triggerToast('EMERGENCY STOP DEPLOYED', 'error');
    // Forward command to ROS via websocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'command',
        action: 'estop',
        param: true
      }));
    }
  };

  // Release E-Stop
  const resetEStop = () => {
    setEStopActive(false);
    addLog('[ESTOP] Emergency stop released. Resuming nominal operation.');
    triggerToast('E-Stop Released', 'success');
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'command',
        action: 'estop',
        param: false
      }));
    }
  };

  // Return to base command
  const returnToBase = () => {
    addLog('[NAV] Manual return-to-base navigation requested.');
    triggerToast('Returning to Base...', 'info');
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'command',
        action: 'return_to_base'
      }));
    }
  };

  // Trigger Auth pinpad for a specific rack lock
  const handleRackUnlockRequest = (rackId: number) => {
    setSelectedRackId(rackId);
    setPinCode('');
    setAuthError('');
    setAuthSuccess(false);
    setShowAuthModal(true);
  };

  // PIN keyboard button action
  const handlePinInput = (char: string) => {
    setAuthError('');
    if (char === 'CLEAR') {
      setPinCode('');
    } else if (char === 'BACK') {
      setPinCode(prev => prev.slice(0, -1));
    } else {
      const isOTP = deliveries.some(d => d.rack_id === selectedRackId && (d.status === 'in_progress' || d.status === 'pending' || d.status === 'arrived'));
      const maxLength = isOTP ? 4 : 8;
      if (pinCode.length < maxLength) {
        setPinCode(prev => prev + char);
      }
    }
  };

  // PIN submission & validation
  const submitPasscode = async () => {
    if (!selectedRackId) return;
    
    // Find active delivery for this rack
    const matchingDelivery = deliveries.find(
      d => d.rack_id === selectedRackId && 
      (d.status === 'in_progress' || d.status === 'pending' || d.status === 'arrived')
    );

    if (matchingDelivery) {
      addLog(`[AUTH] Verifying delivery OTP for Rack ${selectedRackId}...`);
      try {
        const response = await deliveriesApi.verifyDeliveryOTP(matchingDelivery.id, pinCode);
        
        if (response.ok) {
          setAuthSuccess(true);
          addLog(`[AUTH] OTP verification successful. Unlocking Rack ${selectedRackId}...`);
          
          // Perform physical lock unlock
          await rackApi.unlockRack(selectedRackId);
          triggerToast(`Rack ${selectedRackId} Unlocked!`, 'success');
          
          // Clear variables and close modals
          setTimeout(() => {
            setShowAuthModal(false);
            setShowArrivalModal(false);
            setPinCode('');
            setAuthSuccess(false);
          }, 3000);
        }
      } catch (err: any) {
        setAuthError(err.message || 'Incorrect OTP code. Access Denied.');
        addLog(`[AUTH] OTP verification failed for Rack ${selectedRackId}: ${err.message || 'Incorrect OTP'}`);
        triggerToast('Incorrect OTP', 'error');
      }
    } else {
      addLog(`[AUTH] Verifying access passcode for Rack ${selectedRackId}...`);
      try {
        // 1. Verify credentials using backend service
        const response = await rackApi.verifyAccess(selectedRackId, pinCode);
        
        if (response.ok) {
          setAuthSuccess(true);
          addLog(`[AUTH] Verification successful. Unlocking Rack ${selectedRackId}...`);
          
          // 2. Perform physical lock unlock
          await rackApi.unlockRack(selectedRackId);
          triggerToast(`Rack ${selectedRackId} Unlocked!`, 'success');
          
          // Clear variables and close modals
          setTimeout(() => {
            setShowAuthModal(false);
            setPinCode('');
            setAuthSuccess(false);
          }, 3000);
        }
      } catch (err: any) {
        setAuthError(err.message || 'Incorrect passcode. Access Denied.');
        addLog(`[AUTH] Access denied for Rack ${selectedRackId}: ${err.message || 'Verification failure'}`);
        triggerToast('Access Denied', 'error');
      }
    }
  };

  // Re-read DB contents manually
  const forceManualRefresh = async () => {
    addLog('[SYS] Refreshing database records...');
    triggerToast('Refreshed Data', 'info');
    try {
      const [racksData, deliveriesData] = await Promise.all([
        rackApi.getRacks(),
        deliveriesApi.getDeliveries()
      ]);
      setRacks(racksData);
      setDeliveries(deliveriesData);
    } catch (e) {
      addLog('[ERROR] Refresh failed.');
    }
  };

  // State Config mapping
  const config = getRobotStateConfig(currentState);

  // Map user ID to Name
  const getUserName = (id?: number | null) => {
    if (!id) return 'Unassigned';
    const found = users.find(u => u.id === id);
    return found ? found.username : `User #${id}`;
  };

  // Map item ID to Name
  const getItemName = (id?: number | null) => {
    if (!id) return 'Empty';
    const found = inventory.find(i => i.id === id);
    return found ? found.name : `Item #${id}`;
  };

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      background: 'var(--bg-primary)',
      color: 'var(--text-primary)',
      fontFamily: 'var(--font-sans)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      position: 'relative',
    }}>
      
      {/* ─── 1. TOP STATUS BAR ───────────────────────────────────────────────── */}
      <div style={{
        height: '52px',
        background: 'rgba(10, 17, 34, 0.95)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid var(--glass-border)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 10,
      }}>
        {/* Left: Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '10px', height: '10px', borderRadius: '50%',
            background: eStopActive ? 'var(--accent-red)' : (wsConnected ? 'var(--accent-cyan)' : 'var(--text-secondary)'),
            boxShadow: `0 0 10px ${eStopActive ? 'var(--accent-red)' : 'var(--accent-cyan)'}`,
            animation: 'pulse-glow 2s infinite'
          }} />
          <span style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '1px', color: '#fff' }}>
            LAB BUDDY <span style={{ color: 'var(--accent-cyan)' }}>KIOSK</span>
          </span>
        </div>

        {/* Center: Network IP & Cloudflare info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '0.8rem', opacity: 0.85 }}>
          <div>
            <span style={{ color: 'var(--text-secondary)' }}>LOCAL IP: </span>
            <code style={{ fontFamily: 'var(--font-mono)', color: '#fff', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px' }}>{localIp}</code>
          </div>
          {tunnelUrl && (
            <div style={{ display: 'none' /* hidden for compact sizing, but loaded */ }}>
              <span style={{ color: 'var(--text-secondary)' }}>TUNNEL: </span>
              <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-purple)' }}>{tunnelUrl}</code>
            </div>
          )}
        </div>

        {/* Right: Hardware stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.85rem' }}>
          {/* CPU temp */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>CPU:</span>
            <span style={{ 
              fontFamily: 'var(--font-mono)', 
              fontWeight: 600,
              color: telemetry?.cpu_temp > 65 ? 'var(--accent-red)' : (telemetry?.cpu_temp > 50 ? 'var(--accent-yellow)' : 'var(--accent-green)') 
            }}>
              {telemetry?.cpu_temp ? `${telemetry.cpu_temp.toFixed(1)}°C` : '42.0°C'}
            </span>
          </div>

          {/* Battery */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>BATTERY:</span>
            <span style={{ 
              fontFamily: 'var(--font-mono)', 
              fontWeight: 600,
              color: telemetry?.battery <= 20 ? 'var(--accent-red)' : 'var(--accent-green)' 
            }}>
              🔋 {telemetry?.battery ? `${telemetry.battery.toFixed(1)}%` : '100.0%'}
            </span>
          </div>

          {/* Connection */}
          <div style={{
            background: wsConnected ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
            border: `1px solid ${wsConnected ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'}`,
            padding: '2px 8px',
            borderRadius: '20px',
            fontSize: '0.75rem',
            color: wsConnected ? 'var(--accent-green)' : 'var(--accent-red)',
            fontWeight: 600
          }}>
            {wsConnected ? 'LINK ONLINE' : 'LINK OFFLINE'}
          </div>
        </div>
      </div>

      {/* ─── 2. MAIN LAYOUT (DASHBOARD GRID) ─────────────────────────────────── */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '1.2fr 1fr',
        padding: '16px',
        gap: '16px',
        height: 'calc(100vh - 112px)',
        overflow: 'hidden',
      }}>
        
        {/* ── LEFT PANEL: Face, Coordinates, and Mission ── */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
          height: '100%',
        }}>
          {/* Animated Face Frame */}
          <div style={{
            flex: currentState !== RobotState.IDLE ? 'none' : 1,
            position: currentState !== RobotState.IDLE ? 'fixed' : 'relative',
            top: currentState !== RobotState.IDLE ? 0 : 'auto',
            left: currentState !== RobotState.IDLE ? 0 : 'auto',
            width: currentState !== RobotState.IDLE ? '100vw' : 'auto',
            height: currentState !== RobotState.IDLE ? '100vh' : 'auto',
            zIndex: currentState !== RobotState.IDLE ? 40 : 1,
            background: '#000',
            borderRadius: currentState !== RobotState.IDLE ? '0' : '20px',
            overflow: 'hidden',
            border: currentState !== RobotState.IDLE ? 'none' : `2px solid ${config.color}`,
            boxShadow: currentState !== RobotState.IDLE ? 'none' : `0 0 20px ${config.glowColor}`,
          }}>
            <RobotDisplay
              state={currentState}
              height="100%"
              showLabel={false}
              showStatus={false}
              onVideoEnd={() => {
                setCurrentState(RobotState.IDLE);
                setManualOverride(false);
              }}
            />

            {/* Float HUD Details on the Face Display */}
            {currentState === RobotState.IDLE && (
              <div style={{
                position: 'absolute',
                top: '16px',
                left: '16px',
                background: 'rgba(0,0,0,0.7)',
                padding: '6px 14px',
                borderRadius: '20px',
                border: `1px solid ${config.color}`,
                fontSize: '0.8rem',
                fontWeight: 700,
                letterSpacing: '1px',
                color: config.color,
                textTransform: 'uppercase',
              }}>
                STATUS: {config.label}
              </div>
            )}

            {/* Quick manual selection overlay indicator */}
            {manualOverride && currentState === RobotState.IDLE && (
              <div 
                onClick={() => setManualOverride(false)}
                style={{
                  position: 'absolute',
                  top: '16px',
                  right: '16px',
                  background: 'rgba(245,158,11,0.85)',
                  color: '#000',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  letterSpacing: '0.5px'
                }}
              >
                ⚠️ MANUAL OVERRIDE (TAP TO RESET)
              </div>
            )}
          </div>

          {/* Coordinate & Mission sub-panel */}
          <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '6px' }}>
              <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '1px' }}>Active Mission</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                {telemetry?.timestamp || '00:00:00'}
              </span>
            </div>

            <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>
              {telemetry?.mission || 'Standby — Awaiting delivery dispatch'}
            </div>

            {/* Coordinate indicators */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '12px',
              marginTop: '6px',
              background: 'rgba(0,0,0,0.15)',
              padding: '10px',
              borderRadius: '10px',
              border: '1px solid rgba(255,255,255,0.03)'
            }}>
              <div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>COORDINATE X</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#fff', fontSize: '0.95rem' }}>
                  {telemetry?.x !== undefined ? `${telemetry.x.toFixed(3)}m` : '0.000m'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>COORDINATE Y</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#fff', fontSize: '0.95rem' }}>
                  {telemetry?.y !== undefined ? `${telemetry.y.toFixed(3)}m` : '0.000m'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>VELOCITY</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-green)', fontSize: '0.95rem' }}>
                  {currentState === RobotState.NAVIGATING ? '0.62 m/s' : '0.00 m/s'}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL: Racks Status Grid & Event Log ── */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          height: '100%',
          overflow: 'hidden',
        }}>
          {/* Racks Monitor Grid */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}>
            <h3 style={{ fontSize: '0.95rem', letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              Cargo Locker Monitor
            </h3>
            
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '12px',
            }}>
              {[1, 2, 3, 4].map(idx => {
                // Find matching rack
                const r = racks.find(rack => rack.id === idx);
                const isLocked = r ? r.lock_status === 'locked' : true;
                const assignedUser = r ? getUserName(r.assigned_user) : 'Unassigned';
                const assignedItem = r ? getItemName(r.assigned_item) : 'Empty';
                
                return (
                  <div 
                    key={idx}
                    className="glass-panel"
                    style={{
                      padding: '12px 14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      border: `1px solid ${isLocked ? 'rgba(255,255,255,0.06)' : 'var(--accent-green)'}`,
                      boxShadow: isLocked ? 'none' : '0 0 10px rgba(16,185,129,0.2)',
                      background: isLocked ? 'rgba(10, 17, 34, 0.4)' : 'rgba(16,185,129,0.04)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fff' }}>LOCKER 0{idx}</span>
                      <span style={{
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: isLocked ? 'rgba(244,63,94,0.1)' : 'rgba(16,185,129,0.2)',
                        color: isLocked ? 'var(--accent-red)' : 'var(--accent-green)',
                      }}>
                        {isLocked ? '🔒 LOCKED' : '🔓 OPEN'}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.75rem', lineHeight: 1.3 }}>
                      <div style={{ color: 'var(--text-secondary)' }}>Cargo: <span style={{ color: '#fff', fontWeight: 600 }}>{assignedItem}</span></div>
                      <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>Recip: <span style={{ color: 'var(--accent-cyan)', fontWeight: 500 }}>{assignedUser}</span></div>
                    </div>

                    {/* Unlock button */}
                    <button
                      onClick={() => handleRackUnlockRequest(idx)}
                      style={{
                        width: '100%',
                        padding: '8px',
                        borderRadius: '8px',
                        border: '1px solid var(--glass-border)',
                        background: 'rgba(255,255,255,0.04)',
                        color: '#fff',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; e.currentTarget.style.borderColor = 'var(--accent-cyan)'; }}
                      onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.borderColor = 'var(--glass-border)'; }}
                    >
                      🔑 Unlock Touchpad
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Monospace scrolling log event terminal */}
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            overflow: 'hidden',
          }}>
            <h3 style={{ fontSize: '0.95rem', letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              Hardware Event Log
            </h3>
            <div style={{
              flex: 1,
              background: '#020617',
              border: '1px solid var(--glass-border)',
              borderRadius: '16px',
              padding: '12px 16px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.78rem',
              color: 'var(--accent-cyan)',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column-reverse',
              gap: '6px',
              lineHeight: 1.4,
              boxShadow: 'inset 0 0 15px rgba(0,0,0,0.8)'
            }}>
              {logs.map((log, i) => (
                <div key={i} style={{
                  color: log.includes('[ERROR]') ? 'var(--accent-red)' :
                         log.includes('[AUTH]') ? 'var(--accent-purple)' :
                         log.includes('[ARRIVED]') ? 'var(--accent-green)' :
                         log.includes('[NET]') ? '#94a3b8' : 'var(--accent-cyan)'
                }}>
                  {log}
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>

      {/* ─── 3. BOTTOM CONTROL STRIP (FOOTER) ───────────────────────────────── */}
      <div style={{
        height: '60px',
        background: 'rgba(10, 17, 34, 0.95)',
        backdropFilter: 'blur(10px)',
        borderTop: '1px solid var(--glass-border)',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 10,
      }}>
        {/* Left: General operational buttons */}
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            className="btn"
            onClick={returnToBase}
            style={{
              padding: '8px 16px',
              fontSize: '0.85rem',
              background: 'rgba(6, 182, 212, 0.15)',
              borderColor: 'rgba(6, 182, 212, 0.3)',
              color: 'var(--accent-cyan)',
            }}
          >
            🏠 Return to Base
          </button>
          
          <button 
            className="btn"
            onClick={forceManualRefresh}
            style={{
              padding: '8px 16px',
              fontSize: '0.85rem',
              background: 'rgba(255, 255, 255, 0.03)',
              borderColor: 'var(--glass-border)',
              color: 'var(--text-secondary)'
            }}
          >
            🔄 Sync DB
          </button>
        </div>

        {/* Center: Debug preview state options */}
        <div style={{ display: 'flex', gap: '8px', opacity: 0.85 }}>
          {[
            { label: 'Idle', state: RobotState.IDLE, color: '#06b6d4' },
            { label: 'Nav', state: RobotState.NAVIGATING, color: '#2563eb' },
            { label: 'Succ', state: RobotState.TASK_SUCCESS, color: '#10b981' },
            { label: 'Fail', state: RobotState.TASK_FAILED, color: '#f43f5e' },
            { label: 'Chg', state: RobotState.CHARGING, color: '#10b981' },
          ].map(opt => (
            <button
              key={opt.label}
              onClick={() => {
                setManualOverride(true);
                setCurrentState(opt.state);
                addLog(`[MANUAL] Previewing state: ${opt.label}`);
              }}
              style={{
                background: currentState === opt.state ? `${opt.color}22` : 'rgba(255,255,255,0.03)',
                border: `1px solid ${currentState === opt.state ? opt.color : 'rgba(255,255,255,0.06)'}`,
                borderRadius: '6px',
                padding: '2px 8px',
                fontSize: '0.72rem',
                color: currentState === opt.state ? opt.color : 'var(--text-secondary)',
                cursor: 'pointer',
                fontWeight: currentState === opt.state ? 700 : 400
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Right: Giant Emergency E-Stop */}
        <button
          onClick={triggerSoftwareEStop}
          style={{
            height: '42px',
            padding: '0 24px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #ef4444, #b91c1c)',
            border: 'none',
            color: '#fff',
            fontWeight: 800,
            fontSize: '0.9rem',
            letterSpacing: '1px',
            boxShadow: '0 4px 15px rgba(239, 68, 68, 0.4)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          🚨 SOFTWARE E-STOP
        </button>
      </div>

      {/* ─── 4. TRANSIENT TOAST SYSTEM ──────────────────────────────────────── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            style={{
              position: 'absolute',
              bottom: '80px',
              left: '24px',
              background: toast.type === 'error' ? 'var(--accent-red)' :
                          toast.type === 'success' ? 'var(--accent-green)' :
                          toast.type === 'warning' ? 'var(--accent-yellow)' : 'var(--accent-blue)',
              color: '#fff',
              padding: '10px 20px',
              borderRadius: '10px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
              fontWeight: 600,
              fontSize: '0.85rem',
              zIndex: 100,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <span>{toast.type === 'success' ? '✓' : 'ℹ'}</span>
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── 5. FULLSCREEN HAZARD OVERLAY: E-STOP ACTIVE ───────────────────── */}
      <AnimatePresence>
        {eStopActive && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(15, 23, 42, 0.95)',
              zIndex: 200,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '24px',
              border: '6px solid var(--accent-red)',
              boxShadow: 'inset 0 0 100px rgba(244,63,94,0.6)',
            }}
          >
            {/* Flashing Warning Symbol */}
            <motion.div
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              style={{
                width: '100px', height: '100px', borderRadius: '50%',
                background: 'rgba(244,63,94,0.1)',
                border: '4px solid var(--accent-red)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '3rem'
              }}
            >
              🚨
            </motion.div>
            
            <h1 style={{
              fontSize: '2.5rem',
              fontWeight: 800,
              color: 'var(--accent-red)',
              letterSpacing: '2px',
              textAlign: 'center',
              textShadow: '0 0 20px rgba(244,63,94,0.5)'
            }}>
              EMERGENCY STOP ACTIVE
            </h1>

            <p style={{
              maxWidth: '500px',
              textAlign: 'center',
              fontSize: '1.05rem',
              lineHeight: 1.6,
              color: 'var(--text-secondary)'
            }}>
              Hardware Emergency button has been depressed or Software override engaged. All active motor telemetry is halted.
            </p>

            <button
              onClick={resetEStop}
              style={{
                padding: '14px 40px',
                borderRadius: '12px',
                background: '#fff',
                color: '#000',
                border: 'none',
                fontWeight: 700,
                fontSize: '1.1rem',
                cursor: 'pointer',
                boxShadow: '0 10px 20px rgba(255,255,255,0.2)',
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
              onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
            >
              Reset Emergency Control (Clear E-Stop)
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── 6. DELIVERY ARRIVAL RETRIEVAL POPUP ───────────────────────────── */}
      <AnimatePresence>
        {showArrivalModal && arrivedDelivery && !eStopActive && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(5, 11, 20, 0.85)',
              backdropFilter: 'blur(8px)',
              zIndex: 150,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <motion.div
              initial={{ scale: 0.9, y: 50 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 50 }}
              className="glass-panel"
              style={{
                width: '460px',
                padding: '32px',
                border: '1px solid var(--accent-cyan)',
                boxShadow: '0 10px 30px rgba(6,182,212,0.2)',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '3rem' }}>🎁</div>
              <h2 style={{ fontSize: '1.6rem', color: '#fff', fontWeight: 700 }}>
                Delivery Arrived!
              </h2>
              
              <div style={{
                background: 'rgba(0,0,0,0.3)',
                padding: '16px',
                borderRadius: '12px',
                border: '1px solid rgba(255,255,255,0.04)',
                textAlign: 'left',
                fontSize: '0.9rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div><span style={{ color: 'var(--text-secondary)' }}>Recipient: </span><strong>{getUserName(arrivedDelivery.user_id)}</strong></div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Item requested: </span><strong>{getItemName(arrivedDelivery.item_id)}</strong></div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Locker Assigned: </span><span style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>Locker 0{arrivedDelivery.rack_id || 1}</span></div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Destination: </span><strong>{arrivedDelivery.destination || `PC ${arrivedDelivery.pc_no}`}</strong></div>
              </div>

              <div style={{ display: 'flex', gap: '12px', width: '100%', marginTop: '10px' }}>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '12px' }}
                  onClick={() => handleRackUnlockRequest(arrivedDelivery.rack_id || 1)}
                >
                  🔑 Enter OTP to Unlock
                </button>
                <button
                  className="btn"
                  style={{
                    padding: '12px 20px',
                    borderColor: 'var(--glass-border)',
                    background: 'transparent',
                    color: 'var(--text-secondary)'
                  }}
                  onClick={() => setShowArrivalModal(false)}
                >
                  Dismiss
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── 7. PINPAD / PASSCODE VERIFICATION OVERLAY ───────────────────────── */}
      <AnimatePresence>
        {showAuthModal && selectedRackId && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(5, 11, 20, 0.9)',
              backdropFilter: 'blur(10px)',
              zIndex: 180,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <motion.div
              initial={{ scale: 0.9, y: 30 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 30 }}
              className="glass-panel"
              style={{
                width: '380px',
                padding: '24px',
                border: '1px solid var(--glass-border)',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
              }}
            >
              {/* Header */}
              <div style={{ textAlign: 'center' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff' }}>
                  {deliveries.some(d => d.rack_id === selectedRackId && (d.status === 'in_progress' || d.status === 'pending' || d.status === 'arrived'))
                    ? `Locker 0${selectedRackId} OTP Verification`
                    : `Locker 0${selectedRackId} Security Access`}
                </h3>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {deliveries.some(d => d.rack_id === selectedRackId && (d.status === 'in_progress' || d.status === 'pending' || d.status === 'arrived'))
                    ? "Enter the 4-digit OTP shown on your mobile device"
                    : "Enter student password (default: 123456) or staff login PIN"}
                </p>
              </div>

              {/* Password Display Field */}
              <div style={{
                background: 'rgba(0,0,0,0.4)',
                border: `1px solid ${authError ? 'var(--accent-red)' : (authSuccess ? 'var(--accent-green)' : 'var(--glass-border)')}`,
                borderRadius: '12px',
                height: '52px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.4rem',
                letterSpacing: '8px',
                color: authSuccess ? 'var(--accent-green)' : '#fff',
                fontWeight: 700,
                position: 'relative'
              }}>
                {authSuccess ? (
                  <span style={{ letterSpacing: 'normal', fontSize: '1rem' }}>✓ LOCKER UNLOCKED</span>
                ) : (
                  pinCode ? '•'.repeat(pinCode.length) : <span style={{ color: 'rgba(255,255,255,0.15)', letterSpacing: 'normal', fontSize: '0.9rem' }}>Enter Passcode</span>
                )}
              </div>

              {/* Error state */}
              {authError && (
                <div style={{ color: 'var(--accent-red)', fontSize: '0.78rem', textAlign: 'center', fontWeight: 600 }}>
                  ⚠️ {authError}
                </div>
              )}

              {/* Pin Keyboard Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '10px',
              }}>
                {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(char => (
                  <button
                    key={char}
                    disabled={authSuccess}
                    onClick={() => handlePinInput(char)}
                    style={{
                      height: '50px',
                      borderRadius: '8px',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid var(--glass-border)',
                      color: '#fff',
                      fontSize: '1.1rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                    onMouseDown={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                    onMouseUp={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.04)'}
                  >
                    {char}
                  </button>
                ))}
                
                {/* Backspace / 0 / Clear */}
                <button
                  disabled={authSuccess}
                  onClick={() => handlePinInput('CLEAR')}
                  style={{
                    height: '50px',
                    borderRadius: '8px',
                    background: 'rgba(244,63,94,0.1)',
                    border: '1px solid rgba(244,63,94,0.2)',
                    color: 'var(--accent-red)',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  CLEAR
                </button>
                <button
                  disabled={authSuccess}
                  onClick={() => handlePinInput('0')}
                  style={{
                    height: '50px',
                    borderRadius: '8px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid var(--glass-border)',
                    color: '#fff',
                    fontSize: '1.1rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  0
                </button>
                <button
                  disabled={authSuccess}
                  onClick={() => handlePinInput('BACK')}
                  style={{
                    height: '50px',
                    borderRadius: '8px',
                    background: 'rgba(245,158,11,0.1)',
                    border: '1px solid rgba(245,158,11,0.2)',
                    color: 'var(--accent-yellow)',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  BACK
                </button>
              </div>

              {/* Submit Buttons */}
              <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                <button
                  className="btn btn-success"
                  disabled={authSuccess || !pinCode}
                  onClick={submitPasscode}
                  style={{ flex: 1, padding: '12px' }}
                >
                  Verify Code
                </button>
                <button
                  className="btn"
                  disabled={authSuccess}
                  onClick={() => setShowAuthModal(false)}
                  style={{
                    padding: '12px 20px',
                    borderColor: 'var(--glass-border)',
                    background: 'transparent',
                    color: 'var(--text-secondary)'
                  }}
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default RobotDisplayPage;
