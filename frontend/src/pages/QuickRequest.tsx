import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { WorkflowTimeline } from '../components/WorkflowTimeline';
import { RobotStateCard } from '../components/RobotStateCard';
import {
  Smartphone, Monitor, MapPin, Package, Battery, Send,
  ShieldAlert, CheckCircle, Clock, Lock, Unlock, RefreshCw,
  User, LogOut, Compass, Eye, XCircle, AlertTriangle,
  Cpu, Navigation, Sparkles, ArrowRight,
} from 'lucide-react';
import { inventoryApi, deliveriesApi, rackApi } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
  RobotState,
  mapTelemetryToState,
  getRobotStateConfig,
  isErrorState,
  deliveryStatusToStep,
} from '../lib/robotStateLibrary';

// ─── Pickup timeout constants ─────────────────────────────────
const PICKUP_WARNING_SEC = 90;   // Show amber warning
const PICKUP_TIMEOUT_SEC = 120;  // Timeout panel close

export const QuickRequest: React.FC = () => {
  const [username,      setUsername]      = useState(localStorage.getItem('quick_username') || '');
  const [tempUsername,  setTempUsername]  = useState('');
  const [pcNo,          setPcNo]          = useState('');
  const [itemId,        setItemId]        = useState('');
  const [location,      setLocation]      = useState('');
  const [inventory,     setInventory]     = useState<any[]>([]);
  const [recentDeliveries, setRecentDeliveries] = useState<any[]>([]);

  const [phoneNumber,   setPhoneNumber]   = useState(localStorage.getItem('quick_phone_number') || '');
  const [smsNotification, setSmsNotification] = useState<{ message: string; visible: boolean } | null>(null);

  const [loading,         setLoading]        = useState(false);
  const [cancelling,      setCancelling]     = useState(false);
  const [confirming,      setConfirming]     = useState(false);
  const [activeDelivery,  setActiveDelivery] = useState<any>(null);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [showConfirmedSplash, setShowConfirmedSplash] = useState(false);

  // ── Robot Telemetry ───────────────────────────────────────
  const [robotTelemetry, setRobotTelemetry] = useState({
    battery:  100,
    cpu_temp: 40,
    status:   'Idle',
    mission:  'Standby',
    x: 0,
    y: 0,
  });
  const [robotState, setRobotState] = useState<RobotState>(RobotState.IDLE);

  // ── Pickup timeout tracking ───────────────────────────────
  const [pickupElapsed,    setPickupElapsed]    = useState(0);
  const [pickupTimerActive, setPickupTimerActive] = useState(false);
  const pickupTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  // ── Coordinate map helper ─────────────────────────────────
  const mapX = `${50 + (robotTelemetry.x / 5) * 50}%`;
  const mapY = `${50 - (robotTelemetry.y / 5) * 50}%`;

  // ── Data loaders ──────────────────────────────────────────
  const loadInventory = useCallback(() => {
    inventoryApi.getInventory()
      .then(data => setInventory(data.filter((item: any) => item.available && item.quantity > 0)))
      .catch(err => console.error('Failed to load inventory', err));
  }, []);

  const loadRecentDeliveries = useCallback((user: string, forceSetActive = false) => {
    if (!user) return;
    deliveriesApi.getQuickDeliveries(user)
      .then(data => {
        setRecentDeliveries(data);
        const currentActive = data.find((d: any) =>
          d.status === 'pending_approval' || d.status === 'pending' || d.status === 'in_progress' ||
          d.status === 'validating' || d.status === 'task_assigned' ||
          d.status === 'arrived' || d.status === 'panel_open' ||
          d.status === 'waiting_pickup' || d.status === 'pickup_confirmed'
        );
        if (forceSetActive) {
          if (currentActive) {
            setActiveDelivery(currentActive);
          }
        } else {
          setActiveDelivery((current: any) => {
            if (current) {
              if (currentActive && currentActive.id === current.id) {
                return { ...current, ...currentActive };
              }
              return current;
            }
            return currentActive || null;
          });
        }
      })
      .catch(err => console.error('Failed to load recent deliveries', err));
  }, []);

  // ── Pickup timeout timer ──────────────────────────────────
  useEffect(() => {
    const isWaiting =
      robotState === RobotState.ARRIVED ||
      robotState === RobotState.PANEL_OPEN ||
      robotState === RobotState.WAITING_PICKUP;

    if (isWaiting && activeDelivery) {
      setPickupTimerActive(true);
      pickupTimerRef.current = setInterval(() => {
        setPickupElapsed(prev => prev + 1);
      }, 1000);
    } else {
      setPickupTimerActive(false);
      setPickupElapsed(0);
      if (pickupTimerRef.current) clearInterval(pickupTimerRef.current);
    }
    return () => {
      if (pickupTimerRef.current) clearInterval(pickupTimerRef.current);
    };
  }, [robotState, activeDelivery]);

  // ── WebSocket + initial load ──────────────────────────────
  useEffect(() => {
    loadInventory();
    if (username) loadRecentDeliveries(username, true);

    const ws = new WebSocket(
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/ui`
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'telemetry') {
          setRobotTelemetry({
            battery:  data.battery,
            cpu_temp: data.cpu_temp,
            status:   data.status,
            mission:  data.mission,
            x:        data.x,
            y:        data.y,
          });
          const derived = mapTelemetryToState(data.status, data.mission, data.battery);
          setRobotState(derived);
        } else if (data.type === 'delivery_update') {
          if (username) loadRecentDeliveries(username, false);
          setActiveDelivery((current: any) => {
            if (current && data.delivery.id === current.id) {
              return { ...current, ...data.delivery };
            }
            if (!current && data.delivery.username === username) {
              const s = data.delivery.status;
              if (s === 'pending_approval' || s === 'pending' || s === 'in_progress' || s === 'validating' || s === 'task_assigned' ||
                  s === 'arrived' || s === 'panel_open' || s === 'waiting_pickup' || s === 'pickup_confirmed') {
                return data.delivery;
              }
            }
            return current;
          });
        } else if (data.type === 'sms_notification') {
          setSmsNotification({
            message: data.message,
            visible: true
          });
          setTimeout(() => {
            setSmsNotification(prev => prev && prev.message === data.message ? { ...prev, visible: false } : prev);
          }, 8000);
        }
      } catch (err) {
        console.error('WS parsing error:', err);
      }
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [username]);

  // ── Auth handlers ─────────────────────────────────────────
  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (tempUsername.trim()) {
      const formatted = tempUsername.trim().toLowerCase();
      localStorage.setItem('quick_username', formatted);
      setUsername(formatted);
      loadRecentDeliveries(formatted, true);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('quick_username');
    localStorage.removeItem('quick_phone_number');
    setUsername('');
    setPhoneNumber('');
    setActiveDelivery(null);
    setRecentDeliveries([]);
    setMessage(null);
    setPickupElapsed(0);
    setSmsNotification(null);
  };

  // ── Dispatch request ──────────────────────────────────────
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
        pc_no:   pcNo,
        item_id: parseInt(itemId),
        location,
        rack_id: selectedItem?.rack_id || null,
        phone_number: phoneNumber || null
      });
      if (phoneNumber) {
        localStorage.setItem('quick_phone_number', phoneNumber);
      }
      setActiveDelivery(res);
      setShowConfirmedSplash(true);
      setTimeout(() => setShowConfirmedSplash(false), 2500);
      loadInventory();
      loadRecentDeliveries(username, false);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to dispatch robot.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // ── Cancel delivery ───────────────────────────────────────
  const handleCancelDelivery = async () => {
    if (!activeDelivery) return;
    setCancelling(true);
    try {
      await deliveriesApi.cancelDelivery(activeDelivery.id);
      setMessage({ text: 'Delivery cancelled successfully.', type: 'success' });
      setActiveDelivery(null);
      loadRecentDeliveries(username, false);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to cancel delivery.', type: 'error' });
    } finally {
      setCancelling(false);
    }
  };

  // ── Confirm pickup ────────────────────────────────────────
  const handleConfirmPickup = async () => {
    if (!activeDelivery) return;
    setConfirming(true);
    try {
      await deliveriesApi.confirmPickup(activeDelivery.id);
      setMessage({ text: "Item collected! Thank you. Panel closing...", type: 'success' });
      loadRecentDeliveries(username, false);
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to confirm pickup.', type: 'error' });
    } finally {
      setConfirming(false);
    }
  };

  // ── Rack unlock ───────────────────────────────────────────
  const handleUnlockRack = async () => {
    if (!activeDelivery || !activeDelivery.rack_id) return;
    try {
      await rackApi.unlockRack(activeDelivery.rack_id);
      setMessage({ text: `Cabinet Rack ${activeDelivery.rack_id} unlocked!`, type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to unlock rack.', type: 'error' });
    }
  };

  // ── Helpers ───────────────────────────────────────────────
  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed' || s === 'pickup_confirmed') return 'var(--accent-green)';
    if (s === 'in_progress' || s === 'arrived' || s === 'panel_open') return 'var(--accent-blue)';
    if (s === 'pending_approval' || s === 'pending'  || s === 'validating' || s === 'task_assigned') return '#f59e0b';
    if (s === 'waiting_pickup') return '#f59e0b';
    if (s === 'cancelled' || s === 'failed') return 'var(--accent-red)';
    return 'var(--text-secondary)';
  };

  const cfg          = getRobotStateConfig(robotState);
  const isRobotError = isErrorState(robotState);
  const currentStep  = activeDelivery
    ? deliveryStatusToStep(activeDelivery.status, robotState)
    : -1;

  const canCancel   = activeDelivery &&
    (activeDelivery.status === 'pending_approval' || activeDelivery.status === 'pending' || activeDelivery.status === 'validating');
  const canPickup   =
    robotState === RobotState.PANEL_OPEN ||
    robotState === RobotState.WAITING_PICKUP ||
    activeDelivery?.status === 'panel_open' ||
    activeDelivery?.status === 'waiting_pickup';
  const isCompleted = activeDelivery?.status === 'completed' || activeDelivery?.status === 'pickup_confirmed';

  // ETA estimate (rough distance-based if navigating)
  const etaText = (() => {
    if (robotState !== RobotState.NAVIGATING) return null;
    const dist = Math.sqrt(robotTelemetry.x ** 2 + robotTelemetry.y ** 2);
    const etaSec = Math.max(30, Math.round(dist * 60));
    if (etaSec < 60) return `~${etaSec}s`;
    return `~${Math.round(etaSec / 60)}m ${etaSec % 60}s`;
  })();

  // Pickup timeout state
  const isPickupWarning = pickupTimerActive && pickupElapsed >= PICKUP_WARNING_SEC && pickupElapsed < PICKUP_TIMEOUT_SEC;
  const isPickupTimeout = pickupTimerActive && pickupElapsed >= PICKUP_TIMEOUT_SEC;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', padding: '16px', maxWidth: '480px', margin: '0 auto', gap: '16px', position: 'relative' }}>

      {/* ── Incoming SMS Simulation ────────────────────── */}
      <AnimatePresence>
        {smsNotification && smsNotification.visible && (
          <motion.div
            initial={{ opacity: 0, y: -50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -50, scale: 0.9 }}
            style={{
              position: 'fixed',
              top: '16px',
              left: '16px',
              right: '16px',
              maxWidth: '448px',
              margin: '0 auto',
              padding: '16px',
              borderRadius: '16px',
              background: 'rgba(255, 255, 255, 0.98)',
              color: '#111827',
              boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
              borderLeft: '5px solid #2563eb',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              zIndex: 9999,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', fontWeight: 700, color: '#2563eb' }}>
              <Smartphone size={14} /> SMS Notification (Simulated)
              <button 
                onClick={() => setSmsNotification(null)} 
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#6b7280', fontSize: '0.9rem', cursor: 'pointer', fontWeight: 700 }}
              >
                ✕
              </button>
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, lineHeight: 1.4 }}>
              {smsNotification.message}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Header ─────────────────────────────────────────── */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '38px', height: '38px', borderRadius: '12px',
            background: `linear-gradient(135deg, ${cfg.color}, ${cfg.glowColor.replace('rgba', 'rgb').replace(/,\s*[\d.]+\)/, ')')})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 0 14px ${cfg.glowColor}`,
            transition: 'all 0.5s ease',
          }}>
            <Smartphone size={18} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.15rem', margin: 0, fontWeight: 700, letterSpacing: '-0.5px' }}>Lab Buddy</h1>
            <span style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', display: 'block', marginTop: '-2px', fontWeight: 600 }}>
              Mobile Request Portal
            </span>
          </div>
        </div>

        {username && (
          <button onClick={handleLogout} className="btn" style={{
            padding: '6px 10px', background: 'rgba(244, 63, 94, 0.1)',
            color: 'var(--accent-red)', border: '1px solid rgba(244, 63, 94, 0.2)',
            borderRadius: '10px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px',
          }}>
            <LogOut size={14} /> {username}
          </button>
        )}
      </header>

      <AnimatePresence mode="wait">
        {/* ── LOGIN VIEW ───────────────────────────────────── */}
        {!username ? (
          <motion.div
            key="login-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <GlassPanel style={{ padding: '36px 28px', borderRadius: '24px', textAlign: 'center' }}>
              <div style={{
                width: '64px', height: '64px', borderRadius: '20px',
                background: 'rgba(6, 182, 212, 0.1)', border: '1px solid var(--accent-cyan)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px auto',
              }}>
                <User size={32} color="var(--accent-cyan)" />
              </div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>Welcome to Lab Buddy</h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '28px', lineHeight: 1.5 }}>
                Enter your username to access the automated equipment delivery portal.
              </p>
              <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ position: 'relative' }}>
                  <input
                    required type="text" className="input-field"
                    placeholder="Enter Student Username"
                    value={tempUsername} onChange={e => setTempUsername(e.target.value)}
                    style={{ paddingLeft: '46px', textAlign: 'center' }}
                  />
                  <User size={16} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                </div>
                <button type="submit" className="btn btn-primary" style={{ padding: '14px', borderRadius: '12px', width: '100%', fontSize: '0.95rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  <ArrowRight size={16} /> Connect Portal
                </button>
              </form>
            </GlassPanel>
          </motion.div>

        ) : (
          /* ── MAIN DASHBOARD ──────────────────────────────── */
          <motion.div
            key="dashboard-view"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.25 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
          >

            {/* ── Request Confirmed Splash ──────────────────── */}
            <AnimatePresence>
              {showConfirmedSplash && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  style={{
                    position: 'fixed', inset: 0, display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
                    zIndex: 1000,
                  }}
                >
                  <div style={{ textAlign: 'center' }}>
                    <motion.div
                      animate={{ scale: [0.8, 1.2, 1], rotate: [0, 10, -10, 0] }}
                      transition={{ duration: 0.6 }}
                      style={{ fontSize: '4rem', marginBottom: '16px' }}
                    >
                      🚀
                    </motion.div>
                    <h2 style={{ color: 'var(--accent-green)', fontSize: '1.8rem', marginBottom: '8px' }}>Request Confirmed!</h2>
                    <p style={{ color: 'var(--text-secondary)' }}>Robot is being dispatched to your location</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Pickup Timeout Warning ────────────────────── */}
            <AnimatePresence>
              {(isPickupWarning || isPickupTimeout) && (
                <motion.div
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  style={{
                    padding: '14px 16px',
                    borderRadius: '16px',
                    background: isPickupTimeout ? 'rgba(244,63,94,0.15)' : 'rgba(245,158,11,0.15)',
                    border: `1px solid ${isPickupTimeout ? 'rgba(244,63,94,0.4)' : 'rgba(245,158,11,0.4)'}`,
                    display: 'flex', alignItems: 'center', gap: '10px',
                  }}
                >
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ repeat: Infinity, duration: 0.8 }}
                  >
                    <AlertTriangle size={20} color={isPickupTimeout ? 'var(--accent-red)' : '#f59e0b'} />
                  </motion.div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem', color: isPickupTimeout ? 'var(--accent-red)' : '#f59e0b' }}>
                      {isPickupTimeout ? 'Pickup Timeout — Panel Closing' : '⚠️ Panel closing soon!'}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      {isPickupTimeout
                        ? 'Please contact lab staff for assistance.'
                        : `Please collect your item. Closing in ${PICKUP_TIMEOUT_SEC - pickupElapsed}s`}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Global Message ────────────────────────────── */}
            <AnimatePresence>
              {message && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  style={{
                    padding: '12px 16px', borderRadius: '12px', fontSize: '0.85rem',
                    display: 'flex', alignItems: 'center', gap: '8px',
                    background: message.type === 'error' ? 'rgba(244,63,94,0.1)' : 'rgba(16,185,129,0.1)',
                    color: message.type === 'error' ? 'var(--accent-red)' : 'var(--accent-green)',
                    border: `1px solid ${message.type === 'error' ? 'rgba(244,63,94,0.2)' : 'rgba(16,185,129,0.2)'}`,
                  }}
                >
                  <ShieldAlert size={14} />
                  <span>{message.text}</span>
                  <button onClick={() => setMessage(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>✕</button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Live Telemetry Card ───────────────────────── */}
            <GlassPanel style={{
              padding: '18px', borderRadius: '24px',
              border: `1px solid ${cfg.color}30`,
              boxShadow: isRobotError ? `0 0 20px ${cfg.glowColor}` : 'var(--glass-shadow)',
              transition: 'all 0.5s ease',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Compass size={17} color="var(--accent-cyan)" />
                  <h3 style={{ fontSize: '1rem', margin: 0 }}>Live Robot Status</h3>
                </div>
                {/* Robot state badge */}
                <RobotStateCard
                  state={robotState}
                  battery={robotTelemetry.battery}
                  compact
                  showBattery={false}
                />
              </div>

              {/* Radar map */}
              <div style={{
                height: '130px', background: 'rgba(0,0,0,0.4)', borderRadius: '14px',
                border: `1px solid ${cfg.color}20`, position: 'relative',
                overflow: 'hidden', marginBottom: '12px',
                backgroundImage: 'radial-gradient(var(--glass-border) 1px, transparent 1px)',
                backgroundSize: '20px 20px',
              }}>
                {/* Axes */}
                <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '1px', background: 'rgba(255,255,255,0.04)' }} />
                <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: '1px', background: 'rgba(255,255,255,0.04)' }} />
                {/* Radar circles */}
                <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: '70px', height: '70px', borderRadius: '50%', border: `1px dashed ${cfg.color}15` }} />
                <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: '110px', height: '110px', borderRadius: '50%', border: `1px dashed ${cfg.color}08` }} />

                {/* Robot blip */}
                <motion.div
                  style={{
                    position: 'absolute', left: mapX, top: mapY,
                    width: '14px', height: '14px', borderRadius: '50%',
                    background: cfg.color, transform: 'translate(-50%, -50%)',
                    boxShadow: `0 0 16px ${cfg.color}`,
                  }}
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                />

                {/* Labels */}
                <div style={{ position: 'absolute', bottom: '8px', left: '12px', fontSize: '0.72rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                  ({robotTelemetry.x.toFixed(2)}, {robotTelemetry.y.toFixed(2)})
                </div>
                <div style={{ position: 'absolute', bottom: '8px', right: '12px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  <span style={{ color: cfg.color, fontWeight: 600 }}>{robotTelemetry.mission}</span>
                </div>

                {/* ETA chip */}
                {etaText && (
                  <div style={{
                    position: 'absolute', top: '8px', right: '8px',
                    background: 'rgba(37,99,235,0.85)', backdropFilter: 'blur(8px)',
                    padding: '3px 8px', borderRadius: '10px', fontSize: '0.72rem',
                    fontWeight: 700, color: '#fff', display: 'flex', alignItems: 'center', gap: '4px',
                  }}>
                    <Clock size={10} /> ETA {etaText}
                  </div>
                )}
              </div>

              {/* Status pills */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', fontSize: '0.78rem', textAlign: 'center' }}>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.68rem' }}>Battery</div>
                  <div style={{ fontWeight: 700, color: robotTelemetry.battery <= 20 ? 'var(--accent-red)' : 'var(--accent-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '3px' }}>
                    <Battery size={11} /> {robotTelemetry.battery}%
                  </div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.68rem' }}>CPU Temp</div>
                  <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '3px' }}>
                    <Cpu size={11} /> {robotTelemetry.cpu_temp}°C
                  </div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '10px', border: '1px solid var(--glass-border)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.68rem' }}>Queue</div>
                  <div style={{ fontWeight: 700, color: 'var(--accent-purple)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '3px' }}>
                    <Navigation size={11} /> {robotTelemetry.status === 'Idle' ? 'Ready' : 'Active'}
                  </div>
                </div>
              </div>
            </GlassPanel>

            <AnimatePresence mode="wait">
              {/* ── ACTIVE DELIVERY TRACKER ─────────────────── */}
              {activeDelivery ? (
                <motion.div
                  key="active-delivery"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.2 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
                >
                  {/* Delivery tracker card */}
                  <GlassPanel style={{ padding: '22px', borderRadius: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
                      <h3 style={{ fontSize: '1.05rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Compass size={17} color="var(--accent-blue)" /> Track Delivery
                      </h3>
                      <button
                        onClick={() => setActiveDelivery(null)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--accent-cyan)', fontSize: '0.8rem', cursor: 'pointer', fontWeight: 600 }}
                      >
                        New Dispatch
                      </button>
                    </div>

                    {/* 7-step workflow timeline */}
                    <WorkflowTimeline
                      deliveryStatus={activeDelivery.status}
                      robotState={robotState}
                      arrivedAt={activeDelivery.arrived_at}
                    />

                    {/* OTP Display Badge */}
                    {activeDelivery.otp && (activeDelivery.status === 'arrived' || activeDelivery.status === 'panel_open' || activeDelivery.status === 'waiting_pickup') && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        style={{
                          background: 'linear-gradient(135deg, rgba(6,182,212,0.15), rgba(139,92,246,0.15))',
                          border: '1px solid var(--accent-cyan)',
                          borderRadius: '16px',
                          padding: '16px',
                          textAlign: 'center',
                          marginTop: '18px',
                          boxShadow: '0 0 16px rgba(6,182,212,0.25)',
                        }}
                      >
                        <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>
                          🔑 Delivery Retrieval OTP
                        </div>
                        <div className="mono" style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', letterSpacing: '4px' }}>
                          {activeDelivery.otp}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                          Enter this code on the robot's touch screen to open your locker.
                        </div>
                      </motion.div>
                    )}

                    {/* Metadata */}
                    <div style={{
                      background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)',
                      borderRadius: '14px', padding: '12px 16px',
                      display: 'flex', flexDirection: 'column', gap: '7px',
                      fontSize: '0.8rem', marginTop: '18px',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Tracking ID:</span>
                        <span className="mono" style={{ fontWeight: 600 }}>#DEL-{activeDelivery.id}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Equipment:</span>
                        <span style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                          {activeDelivery.item_name || `Item #${activeDelivery.item_id}`}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Destination:</span>
                        <span style={{ fontWeight: 600 }}>{activeDelivery.pc_no} — {activeDelivery.location}</span>
                      </div>
                      {activeDelivery.phone_number && (
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: 'var(--text-secondary)' }}>SMS Alerts:</span>
                          <span style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{activeDelivery.phone_number}</span>
                        </div>
                      )}
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Status:</span>
                        <span style={{ fontWeight: 700, color: getStatusColor(activeDelivery.status) }}>
                          {activeDelivery.status.toUpperCase().replace(/_/g, ' ')}
                        </span>
                      </div>
                      {currentStep >= 0 && !isCompleted && (
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: 'var(--text-secondary)' }}>Progress:</span>
                          <span style={{ fontWeight: 600, color: 'var(--accent-purple)' }}>
                            Step {currentStep + 1} of 7
                          </span>
                        </div>
                      )}
                    </div>
                  </GlassPanel>

                  {/* ── Pickup Confirmation Panel ─────────────── */}
                  <AnimatePresence>
                    {canPickup && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                      >
                        <GlassPanel style={{
                          padding: '20px', borderRadius: '24px',
                          border: '1px solid rgba(16,185,129,0.4)',
                          boxShadow: '0 0 24px rgba(16,185,129,0.2)',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                            <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ repeat: Infinity, duration: 1 }}>
                              <Unlock size={18} color="var(--accent-green)" />
                            </motion.div>
                            <h4 style={{ margin: 0, color: 'var(--accent-green)', fontSize: '1rem' }}>
                              Panel is Open — Collect Your Item
                            </h4>
                          </div>
                          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '14px', lineHeight: 1.4 }}>
                            Your equipment is ready. Please collect it from compartment{' '}
                            {activeDelivery?.rack_id ? <strong>R-{activeDelivery.rack_id}</strong> : 'the open panel'}.
                          </p>
                          <button
                            onClick={handleConfirmPickup}
                            disabled={confirming}
                            className="btn btn-success"
                            style={{ width: '100%', padding: '14px', borderRadius: '12px', fontSize: '0.95rem' }}
                          >
                            {confirming ? (
                              <><RefreshCw size={16} className="spinner" /> Confirming...</>
                            ) : (
                              <><CheckCircle size={16} /> I've Collected My Item</>
                            )}
                          </button>
                        </GlassPanel>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* ── Cabinet Lock Panel ────────────────────── */}
                  {activeDelivery.rack_id && (
                    <GlassPanel style={{
                      padding: '18px', borderRadius: '22px',
                      border: '1px solid rgba(139,92,246,0.3)',
                      boxShadow: '0 0 16px rgba(139,92,246,0.12)',
                    }}>
                      <h4 style={{ fontSize: '0.95rem', margin: '0 0 8px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Lock size={15} color="var(--accent-purple)" /> Cabinet Lock Manager
                      </h4>
                      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '14px', lineHeight: 1.4 }}>
                        When the robot arrives, tap below to unlock your compartment.
                      </p>
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <div style={{
                          flex: 1, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--glass-border)',
                          borderRadius: '10px', padding: '10px', display: 'flex', flexDirection: 'column',
                          alignItems: 'center', justifyContent: 'center',
                        }}>
                          <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>Rack</span>
                          <span className="mono" style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                            R-{activeDelivery.rack_id}
                          </span>
                        </div>
                        <button
                          onClick={handleUnlockRack}
                          disabled={activeDelivery.status === 'cancelled' || activeDelivery.status === 'failed'}
                          className="btn"
                          style={{
                            flex: 1.5,
                            background: 'linear-gradient(135deg, var(--accent-purple), #7c3aed)',
                            color: '#fff', border: 'none',
                            boxShadow: '0 4px 15px rgba(139,92,246,0.4)',
                            opacity: activeDelivery.status === 'cancelled' ? 0.4 : 1,
                          }}
                        >
                          <Unlock size={15} /> Unlock Cabinet
                        </button>
                      </div>
                    </GlassPanel>
                  )}

                  {/* ── Cancel Delivery ───────────────────────── */}
                  {canCancel && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                      <button
                        onClick={handleCancelDelivery}
                        disabled={cancelling}
                        className="btn"
                        style={{
                          width: '100%', padding: '12px', borderRadius: '14px',
                          background: 'rgba(244,63,94,0.08)', color: 'var(--accent-red)',
                          border: '1px solid rgba(244,63,94,0.25)', fontSize: '0.88rem',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                        }}
                      >
                        {cancelling ? (
                          <><RefreshCw size={14} className="spinner" /> Cancelling...</>
                        ) : (
                          <><XCircle size={14} /> Cancel This Request</>
                        )}
                      </button>
                    </motion.div>
                  )}

                  {/* Completed state */}
                  {isCompleted && (
                    <GlassPanel style={{
                      padding: '20px', borderRadius: '20px', textAlign: 'center',
                      border: '1px solid rgba(16,185,129,0.3)',
                      background: 'rgba(16,185,129,0.05)',
                    }}>
                      <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>🎉</div>
                      <h3 style={{ color: 'var(--accent-green)', margin: '0 0 8px 0' }}>Delivery Complete!</h3>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '16px' }}>
                        Your equipment has been delivered successfully.
                      </p>
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button
                          onClick={() => { setActiveDelivery(null); setMessage(null); }}
                          className="btn btn-primary"
                          style={{ flex: 1, padding: '12px', borderRadius: '12px' }}
                        >
                          <Sparkles size={14} /> New Request
                        </button>
                      </div>
                    </GlassPanel>
                  )}
                </motion.div>

              ) : (
                /* ── DISPATCH FORM ──────────────────────────── */
                <motion.div
                  key="dispatch-form"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.2 }}
                >
                  <GlassPanel style={{ padding: '22px', borderRadius: '24px' }}>
                    <h3 style={{ fontSize: '1.15rem', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Send size={17} color="var(--accent-cyan)" /> Dispatch Equipment
                    </h3>

                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '10px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                            Target PC *
                          </label>
                          <div style={{ position: 'relative' }}>
                            <input
                              required type="text" className="input-field"
                              value={pcNo} onChange={e => setPcNo(e.target.value)}
                              placeholder="e.g. PC-14"
                              style={{ paddingLeft: '40px' }}
                            />
                            <Monitor size={13} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                          </div>
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                            Location/Bench *
                          </label>
                          <div style={{ position: 'relative' }}>
                            <input
                              required type="text" className="input-field"
                              value={location} onChange={e => setLocation(e.target.value)}
                              placeholder="e.g. Row B-4"
                              style={{ paddingLeft: '40px' }}
                            />
                            <MapPin size={13} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                          </div>
                        </div>
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                          Mobile Phone Number (Optional, for SMS notifications)
                        </label>
                        <div style={{ position: 'relative' }}>
                          <input
                            type="tel" className="input-field"
                            value={phoneNumber} onChange={e => setPhoneNumber(e.target.value)}
                            placeholder="e.g. +1234567890"
                            style={{ paddingLeft: '40px' }}
                          />
                          <Smartphone size={13} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        </div>
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                          Select Equipment *
                        </label>
                        <div style={{ position: 'relative' }}>
                          <select
                            required className="input-field"
                            value={itemId} onChange={e => setItemId(e.target.value)}
                            style={{ paddingLeft: '40px', appearance: 'none' }}
                          >
                            <option value="">-- Choose Item --</option>
                            {inventory.map(item => (
                              <option key={item.id} value={item.id}>
                                {item.name} ({item.quantity} in stock)
                              </option>
                            ))}
                          </select>
                          <Package size={13} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        </div>
                      </div>

                      {/* Robot availability warning */}
                      {robotTelemetry.battery <= 15 && (
                        <div style={{
                          padding: '10px 14px', borderRadius: '10px', fontSize: '0.8rem',
                          background: 'rgba(245,158,11,0.1)', color: '#f59e0b',
                          border: '1px solid rgba(245,158,11,0.2)',
                          display: 'flex', alignItems: 'center', gap: '8px',
                        }}>
                          <AlertTriangle size={14} />
                          Robot battery is low. Requests may be queued until charging completes.
                        </div>
                      )}

                      <button
                        type="submit" disabled={loading}
                        className="btn btn-primary"
                        style={{ width: '100%', padding: '14px', borderRadius: '12px', fontSize: '0.95rem', marginTop: '4px' }}
                      >
                        {loading ? (
                          <><RefreshCw size={16} className="spinner" /> Dispatching...</>
                        ) : (
                          <><Send size={16} /> Request Robot Delivery</>
                        )}
                      </button>
                    </form>
                  </GlassPanel>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Recent Requests Log ───────────────────────── */}
            {recentDeliveries.length > 0 && (
              <GlassPanel style={{ padding: '18px', borderRadius: '22px' }}>
                <h3 style={{ fontSize: '0.95rem', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Clock size={15} color="var(--accent-blue)" /> Your Request History
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto' }}>
                  {recentDeliveries.map((delivery) => (
                    <div
                      key={delivery.id}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '10px 12px',
                        background: activeDelivery?.id === delivery.id ? `rgba(6,182,212,0.06)` : 'rgba(0,0,0,0.12)',
                        borderRadius: '12px',
                        border: activeDelivery?.id === delivery.id ? '1px solid var(--accent-cyan)' : '1px solid var(--glass-border)',
                        transition: 'all 0.2s',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600 }} className="mono">#DEL-{delivery.id}</div>
                        {/* Compact progress pills */}
                        <WorkflowTimeline
                          deliveryStatus={delivery.status}
                          robotState={activeDelivery?.id === delivery.id ? robotState : RobotState.IDLE}
                          compact
                          showLabels={false}
                        />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          fontSize: '0.72rem', fontWeight: 600,
                          color: getStatusColor(delivery.status),
                          background: `${getStatusColor(delivery.status)}15`,
                          padding: '2px 8px', borderRadius: '6px',
                        }}>
                          {delivery.status.toUpperCase().replace(/_/g, ' ')}
                        </span>
                        {activeDelivery?.id !== delivery.id &&
                         (delivery.status === 'pending' || delivery.status === 'in_progress' ||
                          delivery.status === 'arrived' || delivery.status === 'panel_open') && (
                          <button
                            onClick={() => { setActiveDelivery(delivery); setMessage(null); }}
                            className="btn"
                            style={{ padding: '5px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}
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
