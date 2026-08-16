import React, { useState, useEffect } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { 
  Package, LogOut, CheckCircle2, Mail, ShieldCheck, 
  Clock, Lock, Unlock, AlertCircle, Send
} from 'lucide-react';
import { inventoryApi, deliveriesApi, configApi } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';

export const UserDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  
  const [inventory, setInventory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [location, setLocation] = useState('Lab Desk 1');
  const [pcNo, setPcNo] = useState('PC-01');
  
  const [activeDelivery, setActiveDelivery] = useState<any>(null);
  const [otpInput, setOtpInput] = useState('');
  const [otpVerifying, setOtpVerifying] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [flapUnlocked, setFlapUnlocked] = useState(false);
  const [config, setConfig] = useState<any>(null);

  const userEmail = user?.profile?.email || (user?.username?.includes('@') ? user.username : `${user?.username || 'user'}@lab.com`);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const loadInventory = async () => {
    try {
      setLoading(true);
      const data = await inventoryApi.getInventory();
      const available = data.filter((item: any) => item.available && item.quantity > 0);
      setInventory(available);
      if (available.length > 0 && !selectedItemId) {
        setSelectedItemId(available[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadActiveDelivery = async () => {
    if (!user?.username) return;
    try {
      const data = await deliveriesApi.getQuickDeliveries(user.username);
      const active = data.find((d: any) => 
        ['pending', 'pending_approval', 'in_progress', 'task_assigned', 'arrived', 'waiting_pickup', 'panel_open'].includes(d.status)
      );
      setActiveDelivery(active || null);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    configApi.getConfig().then(setConfig).catch(console.error);
    loadInventory();
    loadActiveDelivery();

    // Setup polling for active delivery status updates
    const interval = setInterval(() => {
      loadActiveDelivery();
    }, 3000);

    return () => clearInterval(interval);
  }, [user]);

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItemId) {
      setMessage({ text: 'Please select an item from the catalog', type: 'error' });
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const selectedItem = inventory.find(i => i.id === selectedItemId);
      const res = await deliveriesApi.requestQuickItem({
        username: user?.username || 'user',
        pc_no: pcNo,
        item_id: selectedItemId,
        location: location,
        rack_id: selectedItem?.rack_id || null,
        email: userEmail
      });
      setActiveDelivery(res);
      setMessage({ text: `Order placed! Robot dispatched to ${location}. Check your Mail ID for OTP when robot arrives.`, type: 'success' });
      loadInventory();
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to place order', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDelivery || !otpInput.trim()) return;

    setOtpVerifying(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/v1/deliveries/${activeDelivery.id}/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ otp: otpInput.trim() })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Invalid OTP code');
      }

      setFlapUnlocked(true);
      setMessage({ text: '✅ OTP Verified! Robot Flap Unlocked. Please collect your equipment.', type: 'success' });
      setOtpInput('');
      loadActiveDelivery();
    } catch (err: any) {
      setMessage({ text: err.message || 'Verification failed. Please check the OTP sent to your email.', type: 'error' });
    } finally {
      setOtpVerifying(false);
    }
  };

  if (config?.maintenance_mode) {
    return (
      <div className="flex-center" style={{ minHeight: '100vh', flexDirection: 'column', gap: '24px', padding: '24px', textAlign: 'center' }}>
        <AlertCircle size={80} color="var(--accent-red)" />
        <h1 style={{ color: 'var(--accent-red)' }}>System Under Maintenance</h1>
        <p style={{ maxWidth: '600px', color: 'var(--text-secondary)' }}>
          Lab Buddy operations are currently suspended for manual servicing by administrators.
        </p>
        <button onClick={handleLogout} className="btn" style={{ background: 'rgba(255,255,255,0.1)' }}>
          Logout
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px 20px', minHeight: '100vh' }}>
      
      {/* ── User Header ──────────────────────────────────────── */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '50px', height: '50px', borderRadius: '16px',
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 'bold', fontSize: '1.4rem', color: '#fff',
            boxShadow: '0 0 15px rgba(6, 182, 212, 0.4)'
          }}>
            <Mail size={24} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.6rem', margin: 0, fontWeight: 700 }}>Lab Buddy User Node</h2>
            <div style={{ color: 'var(--accent-cyan)', fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <ShieldCheck size={14} /> Registered Mail ID: <strong>{userEmail}</strong>
            </div>
          </div>
        </div>

        <button 
          onClick={handleLogout} 
          className="btn" 
          style={{ background: 'rgba(244, 63, 94, 0.1)', color: 'var(--accent-red)', border: '1px solid rgba(244, 63, 94, 0.2)', padding: '10px 18px', borderRadius: '12px' }}
        >
          <LogOut size={18} /> <span style={{ marginLeft: '6px' }}>Logout</span>
        </button>
      </header>

      {/* ── Message Alert ───────────────────────────────────── */}
      <AnimatePresence>
        {message && (
          <motion.div 
            initial={{ opacity: 0, y: -15 }} 
            animate={{ opacity: 1, y: 0 }} 
            exit={{ opacity: 0 }}
            style={{ 
              padding: '16px 20px', 
              marginBottom: '24px', 
              borderRadius: '12px',
              background: message.type === 'error' ? 'rgba(244,63,94,0.15)' : 'rgba(16,185,129,0.15)',
              color: message.type === 'error' ? 'var(--accent-red)' : 'var(--accent-green)',
              border: `1px solid ${message.type === 'error' ? 'rgba(244,63,94,0.3)' : 'rgba(16,185,129,0.3)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between'
            }}
          >
            <span>{message.text}</span>
            <button onClick={() => setMessage(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}>✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      <div style={{ display: 'grid', gridTemplateColumns: activeDelivery ? '1fr 1fr' : '1fr', gap: '28px' }}>

        {/* ── Order Equipment Section ────────────────────────── */}
        <GlassPanel style={{ padding: '32px', borderRadius: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
            <Package size={28} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '1.4rem', margin: 0, color: 'var(--accent-cyan)' }}>Order Lab Equipment</h3>
          </div>
          
          <p style={{ color: 'var(--text-secondary)', marginBottom: '24px', fontSize: '0.95rem', lineHeight: 1.5 }}>
            Select required items from the repository inventory. The autonomous robot will deliver them directly to your specified desk.
          </p>

          <form onSubmit={handlePlaceOrder} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase' }}>
                Select Equipment
              </label>
              {loading ? (
                <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading catalog...</div>
              ) : inventory.length === 0 ? (
                <div style={{ padding: '16px', textAlign: 'center', color: 'var(--accent-red)', background: 'rgba(244,63,94,0.1)', borderRadius: '10px' }}>
                  No available items in stock currently.
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
                  {inventory.map(item => (
                    <div 
                      key={item.id}
                      onClick={() => setSelectedItemId(item.id)}
                      style={{
                        padding: '16px',
                        borderRadius: '14px',
                        border: selectedItemId === item.id ? '2px solid var(--accent-cyan)' : '1px solid var(--glass-border)',
                        background: selectedItemId === item.id ? 'rgba(6, 182, 212, 0.15)' : 'rgba(0, 0, 0, 0.2)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: '1.05rem', color: '#fff', marginBottom: '4px' }}>{item.name}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--accent-green)' }}>{item.quantity} in stock</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase' }}>
                  Delivery Room / Desk
                </label>
                <input 
                  type="text" 
                  className="input-field" 
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  placeholder="e.g. Lab 101, Physics Desk"
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase' }}>
                  Station / PC Number
                </label>
                <input 
                  type="text" 
                  className="input-field" 
                  value={pcNo}
                  onChange={e => setPcNo(e.target.value)}
                  placeholder="e.g. PC-04"
                  required
                />
              </div>
            </div>

            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={loading || inventory.length === 0}
              style={{ padding: '16px', fontSize: '1.05rem', borderRadius: '14px', marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
            >
              <Send size={20} /> Request Robot Delivery
            </button>
          </form>
        </GlassPanel>

        {/* ── Active Order & Mail OTP Flap Unlock Section ────────────── */}
        {activeDelivery && (
          <GlassPanel style={{ padding: '32px', borderRadius: '24px', border: '1px solid var(--accent-cyan)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Clock size={24} color="var(--accent-cyan)" />
                <h3 style={{ fontSize: '1.3rem', margin: 0 }}>Active Delivery Status</h3>
              </div>
              <span className="mono" style={{ background: 'rgba(6,182,212,0.2)', color: 'var(--accent-cyan)', padding: '4px 10px', borderRadius: '8px', fontSize: '0.8rem', fontWeight: 600 }}>
                #DEL-{activeDelivery.id}
              </span>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '16px', marginBottom: '24px', border: '1px solid var(--glass-border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Equipment:</span>
                <span style={{ fontWeight: 700, color: '#fff' }}>{activeDelivery.item_name || `Item #${activeDelivery.item_id}`}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Destination:</span>
                <span style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{activeDelivery.location} ({activeDelivery.pc_no})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Status:</span>
                <span style={{ fontWeight: 700, textTransform: 'uppercase', color: activeDelivery.status === 'arrived' ? 'var(--accent-green)' : '#f59e0b' }}>
                  {activeDelivery.status.replace('_', ' ')}
                </span>
              </div>
            </div>

            {/* ── Mail OTP Flap Unlock Form ───────────────────────── */}
            <div style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.1), rgba(37,99,235,0.1))', padding: '24px', borderRadius: '20px', border: '1px solid var(--accent-blue)', textAlign: 'center' }}>
              <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: flapUnlocked ? 'rgba(16,185,129,0.2)' : 'rgba(6,182,212,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                {flapUnlocked ? <Unlock size={24} color="var(--accent-green)" /> : <Lock size={24} color="var(--accent-cyan)" />}
              </div>

              <h4 style={{ fontSize: '1.2rem', margin: '0 0 6px 0', color: flapUnlocked ? 'var(--accent-green)' : '#fff' }}>
                {flapUnlocked ? 'Flap Unlocked & Open!' : 'Enter Mail OTP to Open Flap'}
              </h4>

              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '20px', lineHeight: 1.4 }}>
                An authentication OTP has been sent to <strong>{userEmail}</strong>. Enter the OTP code to disengage the physical flap.
              </p>

              {!flapUnlocked ? (
                <form onSubmit={handleVerifyOtp} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <input 
                    type="text" 
                    className="input-field" 
                    placeholder="Enter Mail OTP Code"
                    value={otpInput}
                    onChange={e => setOtpInput(e.target.value)}
                    style={{ textAlign: 'center', fontSize: '1.4rem', letterSpacing: '4px', fontWeight: 'bold' }}
                    required
                  />

                  <button 
                    type="submit" 
                    className="btn btn-primary"
                    disabled={otpVerifying}
                    style={{ padding: '14px', borderRadius: '12px', fontSize: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                  >
                    {otpVerifying ? 'Verifying...' : 'Verify OTP & Open Flap'}
                  </button>
                </form>
              ) : (
                <div style={{ padding: '12px', background: 'rgba(16,185,129,0.2)', borderRadius: '12px', color: 'var(--accent-green)', fontWeight: 600 }}>
                  <CheckCircle2 size={20} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '6px' }} />
                  Flap is open. Take your equipment and close the panel.
                </div>
              )}
            </div>
          </GlassPanel>
        )}

      </div>
    </div>
  );
};
