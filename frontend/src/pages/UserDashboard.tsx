import React, { useState, useEffect } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Package, LockOpen, LogOut, RefreshCcw, Box, ShieldAlert, Plus, Minus, Server } from 'lucide-react';
import { inventoryApi, rackApi, configApi } from '../services/api';
import { motion, AnimatePresence } from 'framer-motion';

export const UserDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('rack');
  const [inventory, setInventory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [config, setConfig] = useState<any>(null);
  
  // Rack Access State
  const [selectedRack, setSelectedRack] = useState<number | null>(null);
  const [authPassword, setAuthPassword] = useState('');
  const [isRackUnlocked, setIsRackUnlocked] = useState(false);
  const [transactionQuantity, setTransactionQuantity] = useState(1);
  const [selectedItem, setSelectedItem] = useState<number | null>(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const loadInventory = async () => {
    try {
      setLoading(true);
      const data = await inventoryApi.getInventory();
      setInventory(data);
      if (data.length > 0 && !selectedItem) {
        setSelectedItem(data[0].id);
      }
    } catch (err) {
      console.error(err);
      setMessage("Failed to load inventory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Fetch config to check for maintenance mode
    configApi.getConfig().then(setConfig).catch(console.error);

    if (activeTab === 'inventory' || activeTab === 'rack') {
      loadInventory();
    }
  }, [activeTab]);

  const handleRequestItem = async (itemId: number) => {
    try {
      setMessage("Requesting delivery protocol...");
      await inventoryApi.requestItem(itemId, "Lab Desk");
      setMessage("Item requested successfully! Robotic unit dispatched.");
      loadInventory();
      setTimeout(() => setMessage(''), 4000);
    } catch (err) {
      setMessage("Delivery protocol failed. Item unavailable.");
      setTimeout(() => setMessage(''), 4000);
    }
  };

  const handleVerifyRack = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRack) return;
    try {
      setMessage(`Verifying access credentials for Rack ${selectedRack}...`);
      await rackApi.verifyAccess(selectedRack, authPassword);
      await rackApi.unlockRack(selectedRack);
      setIsRackUnlocked(true);
      setMessage(`Authorization granted. Rack ${selectedRack} unlocked.`);
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(`Authentication failed. Unauthorized access.`);
      setTimeout(() => setMessage(''), 4000);
    }
  };

  const handleLogTransaction = async (action: 'add' | 'remove') => {
    if (!selectedRack || !selectedItem) return;
    try {
      setMessage(`Processing ${action} transaction...`);
      await rackApi.logTransaction(selectedRack, selectedItem, action, transactionQuantity);
      setMessage(`Successfully logged ${action} of ${transactionQuantity} unit(s)`);
      loadInventory();
      setTransactionQuantity(1);
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(`Transaction failed: ${(err as Error).message}`);
      setTimeout(() => setMessage(''), 4000);
    }
  };

  const handleCloseRack = async () => {
    if (selectedRack) {
      await rackApi.lockRack(selectedRack);
    }
    setSelectedRack(null);
    setIsRackUnlocked(false);
    setAuthPassword('');
  };

  if (config?.maintenance_mode) {
    return (
      <div className="flex-center" style={{ minHeight: '100vh', flexDirection: 'column', gap: '24px', padding: '24px', textAlign: 'center' }}>
        <ShieldAlert size={80} color="var(--accent-red)" style={{ animation: 'pulse-glow 2s infinite' }} />
        <h1 style={{ color: 'var(--accent-red)' }}>System Under Maintenance</h1>
        <p style={{ maxWidth: '600px', color: 'var(--text-secondary)' }}>
          LabRobot operations are currently suspended for manual servicing by administrators. All delivery and rack access protocols are temporarily offline.
        </p>
        <button onClick={handleLogout} className="btn" style={{ background: 'rgba(255,255,255,0.1)' }}>
          Logout
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '40px 24px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '16px', background: 'linear-gradient(135deg, var(--accent-purple), var(--accent-blue))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '1.5rem', boxShadow: '0 0 20px var(--accent-purple-glow)' }}>
            {user?.username.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 style={{ fontSize: '2rem', margin: 0 }}>Welcome, {user?.username}</h2>
            <span style={{ color: 'var(--accent-blue)', letterSpacing: '1px', textTransform: 'uppercase', fontSize: '0.85rem', fontWeight: 600 }}>LabRobot Secure Terminal</span>
          </div>
        </div>
        <button onClick={handleLogout} className="btn" style={{ background: 'rgba(244, 63, 94, 0.1)', color: 'var(--accent-red)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
          <LogOut size={20} /> <span style={{ marginLeft: '8px' }}>Disconnect</span>
        </button>
      </header>

      <div style={{ display: 'flex', gap: '16px', marginBottom: '3rem' }}>
        <button 
          className={`btn ${activeTab === 'rack' ? 'btn-primary' : ''}`}
          style={{ background: activeTab === 'rack' ? '' : 'rgba(255,255,255,0.05)' }}
          onClick={() => { setActiveTab('rack'); handleCloseRack(); }}
        >
          <LockOpen size={18} /> Access Racks
        </button>
        <button 
          className={`btn ${activeTab === 'inventory' ? 'btn-primary' : ''}`}
          style={{ background: activeTab === 'inventory' ? '' : 'rgba(255,255,255,0.05)' }}
          onClick={() => setActiveTab('inventory')}
        >
          <Package size={18} /> Catalog
        </button>
      </div>
      
      <AnimatePresence>
        {message && (
          <motion.div 
            initial={{ opacity: 0, y: -20 }} 
            animate={{ opacity: 1, y: 0 }} 
            exit={{ opacity: 0, scale: 0.95 }}
            style={{ padding: '16px 24px', marginBottom: '24px', background: 'rgba(37, 99, 235, 0.15)', borderLeft: '4px solid var(--accent-blue)', borderRadius: '8px', backdropFilter: 'blur(10px)', color: '#fff' }}
          >
            {message}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {activeTab === 'rack' && !selectedRack && (
          <motion.div key="rack_selection" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <h3 style={{ marginBottom: '2rem', textAlign: 'center', fontSize: '1.5rem' }}>Select Physical Node</h3>
            <div className="grid-cols-4" style={{ gap: '24px' }}>
              {[1, 2, 3, 4].map(rackId => (
                <GlassPanel 
                  key={rackId} 
                  className="hover-scale"
                  style={{ cursor: 'pointer', textAlign: 'center', padding: '40px 20px', background: 'rgba(0,0,0,0.3)' }}
                  onClick={() => setSelectedRack(rackId)}
                >
                  <Server size={56} color="var(--accent-cyan)" style={{ margin: '0 auto 1.5rem', opacity: 0.8 }} />
                  <h3 style={{ fontSize: '1.4rem' }}>Rack Unit {rackId}</h3>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Initialize Handshake</span>
                </GlassPanel>
              ))}
            </div>
          </motion.div>
        )}

        {activeTab === 'rack' && selectedRack && !isRackUnlocked && (
          <motion.div key="rack_auth" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}>
            <GlassPanel style={{ maxWidth: '500px', margin: '0 auto', textAlign: 'center', padding: '48px 32px' }}>
              <ShieldAlert size={56} color="var(--accent-blue)" style={{ margin: '0 auto 1.5rem' }} />
              <h2 style={{ marginBottom: '1rem', fontSize: '1.8rem' }}>Authorization Required</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '2.5rem', lineHeight: '1.6' }}>
                Secure access protocol initiated for <strong>Rack {selectedRack}</strong>. Please provide your security credentials to disengage the physical locking mechanism.
              </p>
              <form onSubmit={handleVerifyRack} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <input 
                  type="password" 
                  className="input-field" 
                  placeholder="Enter security passphrase" 
                  value={authPassword}
                  onChange={e => setAuthPassword(e.target.value)}
                  style={{ textAlign: 'center', fontSize: '1.1rem', letterSpacing: '2px' }}
                  required
                />
                <div style={{ display: 'flex', gap: '16px', marginTop: '12px' }}>
                  <button type="button" onClick={handleCloseRack} className="btn" style={{ flex: 1, background: 'rgba(255,255,255,0.05)' }}>
                    Abort
                  </button>
                  <button type="submit" className="btn btn-primary" style={{ flex: 2 }}>
                    Disengage Lock
                  </button>
                </div>
              </form>
            </GlassPanel>
          </motion.div>
        )}

        {activeTab === 'rack' && selectedRack && isRackUnlocked && (
          <motion.div key="rack_unlocked" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <GlassPanel style={{ maxWidth: '800px', margin: '0 auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ background: 'rgba(16, 185, 129, 0.2)', padding: '12px', borderRadius: '50%', boxShadow: '0 0 15px var(--accent-green-glow)' }}>
                    <LockOpen size={32} color="var(--accent-green)" />
                  </div>
                  <div>
                    <h2 style={{ margin: 0 }}>Rack {selectedRack} Active</h2>
                    <span style={{ color: 'var(--accent-green)', fontSize: '0.9rem' }}>Locking mechanism disengaged</span>
                  </div>
                </div>
                <button onClick={handleCloseRack} className="btn btn-danger" style={{ display: 'flex', gap: '8px' }}>
                  <span>Seal Rack</span>
                </button>
              </div>

              <h3 style={{ marginBottom: '1rem', fontSize: '1.4rem' }}>Transaction Logging</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
                Please precisely record any physical additions or removals from the rack to maintain database integrity.
              </p>

              <div style={{ display: 'flex', gap: '20px', marginBottom: '2.5rem', flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 300px' }}>
                  <label style={{ display: 'block', marginBottom: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontSize: '0.85rem', letterSpacing: '1px' }}>Target Item</label>
                  <select 
                    className="input-field" 
                    value={selectedItem || ''} 
                    onChange={(e) => setSelectedItem(Number(e.target.value))}
                  >
                    {inventory.map(item => (
                      <option key={item.id} value={item.id}>{item.name} ({item.quantity} in system)</option>
                    ))}
                  </select>
                </div>
                
                <div style={{ flex: '0 0 150px' }}>
                  <label style={{ display: 'block', marginBottom: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontSize: '0.85rem', letterSpacing: '1px' }}>Quantity</label>
                  <input 
                    type="number" 
                    className="input-field" 
                    min="1" 
                    value={transactionQuantity} 
                    onChange={e => setTransactionQuantity(Number(e.target.value))} 
                    style={{ textAlign: 'center' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '20px' }}>
                <button onClick={() => handleLogTransaction('add')} className="btn" style={{ flex: 1, background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-green)', border: '1px solid rgba(16,185,129,0.3)', height: '60px' }}>
                  <Plus size={24} /> <span style={{ fontSize: '1.1rem' }}>Deposit Item</span>
                </button>
                <button onClick={() => handleLogTransaction('remove')} className="btn" style={{ flex: 1, background: 'rgba(244, 63, 94, 0.15)', color: 'var(--accent-red)', border: '1px solid rgba(244,63,94,0.3)', height: '60px' }}>
                  <Minus size={24} /> <span style={{ fontSize: '1.1rem' }}>Extract Item</span>
                </button>
              </div>
            </GlassPanel>
          </motion.div>
        )}

        {activeTab === 'inventory' && (
          <motion.div key="inventory" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="grid-cols-2">
              {loading ? (
                <div className="flex-center" style={{ gridColumn: 'span 2', padding: '4rem', flexDirection: 'column', gap: '16px' }}>
                  <RefreshCcw className="spinner" size={40} color="var(--accent-blue)" /> 
                  <span style={{ color: 'var(--text-secondary)' }}>Synchronizing catalog...</span>
                </div>
              ) : inventory.length === 0 ? (
                <div style={{ gridColumn: 'span 2', textAlign: 'center', color: 'var(--text-secondary)', padding: '4rem' }}>Database is empty.</div>
              ) : inventory.map(item => (
                <GlassPanel key={item.id} className="hover-scale" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px' }}>
                  <div>
                    <h3 style={{ marginBottom: '8px', fontSize: '1.3rem' }}>{item.name}</h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className="status-indicator" style={{ background: item.available ? 'var(--accent-green)' : 'var(--accent-red)' }}></div>
                      <span className="mono" style={{ fontSize: '0.95rem', color: item.available ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                        {item.quantity} Units Available
                      </span>
                    </div>
                  </div>
                  <button 
                    onClick={() => handleRequestItem(item.id)}
                    className="btn btn-primary" 
                    disabled={!item.available || item.quantity <= 0}
                    style={{ opacity: (!item.available || item.quantity <= 0) ? 0.3 : 1, padding: '12px 20px' }}
                  >
                    Request Delivery
                  </button>
                </GlassPanel>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
