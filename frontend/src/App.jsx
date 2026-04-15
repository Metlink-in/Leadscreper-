import React, { useState } from 'react';
import axios from 'axios';
import { 
  Search, 
  MapPin, 
  Phone, 
  Globe, 
  Star, 
  Download, 
  ExternalLink,
  ShieldCheck,
  TrendingUp,
  Loader2,
  X,
  Zap,
  Target,
  Users,
  Briefcase,
  Layers,
  FileJson,
  FileSpreadsheet,
  FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = "http://localhost:8000";

const CATEGORIES = [
  { id: 'Direct Clients', label: 'Direct Clients', icon: <Target size={16} /> },
  { id: 'Startups/Partners', label: 'Startups/Partners', icon: <Layers size={16} /> },
  { id: 'Freelancers', label: 'Freelancers', icon: <Users size={16} /> }
];

const HIGH_VALUE_REGIONS = [
  "USA", "United Kingdom", "Canada", "Australia", "UAE", "Germany", "Singapore"
];

const App = () => {
  const [requirement, setRequirement] = useState('');
  const [location, setLocation] = useState('');
  const [category, setCategory] = useState('Direct Clients');
  const [engine, setEngine] = useState('ddgs'); // Default to free working engine
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refining, setRefining] = useState(false);
  const [exportModal, setExportModal] = useState(false);
  const [sheetId, setSheetId] = useState('');
  const [exportLoading, setExportLoading] = useState(false);
  const [exportStatus, setExportStatus] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!requirement) return;
    setLoading(true);
    setRefining(true);
    try {
      const refineRes = await axios.get(`${API_BASE}/refine-query`, {
        params: { requirement, category }
      });
      const optimizedQuery = refineRes.data.query;
      const searchRes = await axios.get(`${API_BASE}/search`, {
        params: { q: optimizedQuery, location: location, engine: engine }
      });
      setLeads(searchRes.data.leads);
    } catch (err) {
      alert("Search failed. Check if backend is running.");
    } finally {
      setLoading(false);
      setRefining(false);
    }
  };

  const exportToCSV = () => {
    const headers = ["Title", "Address", "Phone", "Website", "Rating", "Reviews", "Category"];
    const csvContent = [
      headers.join(","),
      ...leads.map(l => [
        `"${l.title}"`,
        `"${l.address || ''}"`,
        `"${l.phone || ''}"`,
        `"${l.website || ''}"`,
        l.rating || '0',
        l.reviews || '0',
        category
      ].join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `leads_${category.toLowerCase().replace(' ', '_')}.csv`;
    a.click();
  };

  const exportToJSON = () => {
    const blob = new Blob([JSON.stringify(leads, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `leads_${category.toLowerCase().replace(' ', '_')}.json`;
    a.click();
  };

  const handleGoogleSheetsExport = async (e) => {
    e.preventDefault();
    if (!sheetId || leads.length === 0) return;
    setExportLoading(true);
    try {
      const response = await axios.post(`${API_BASE}/export`, {
        leads: leads,
        spreadsheet_id: sheetId
      });
      if (response.data.error) {
        alert(response.data.error);
      } else {
        setExportStatus("Success! Synced to Google Sheets.");
        setTimeout(() => {
          setExportModal(false);
          setExportStatus(null);
        }, 2000);
      }
    } catch (err) {
      alert("Export failed.");
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header" style={{ marginBottom: '2rem' }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}
        >
          <div className="glass" style={{ padding: '0.4rem 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)', fontSize: '0.75rem', fontWeight: '800', borderRadius: '2rem' }}>
            <Zap size={14} fill="currentColor" /> GLOBAL AGENCY ENGINE
          </div>
        </motion.div>
        
        <motion.h1 
          className="title"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ fontSize: '2.5rem' }}
        >
          LeadScraper <span style={{ color: 'var(--primary)' }}>Agency Pro</span>
        </motion.h1>
      </header>

      {/* Category Tabs */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginBottom: '2rem' }}>
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setCategory(cat.id)}
            className={`glass ${category === cat.id ? 'active-tab' : ''}`}
            style={{
              padding: '0.8rem 1.2rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.9rem',
              background: category === cat.id ? 'var(--primary)' : 'rgba(30, 41, 59, 0.4)',
              border: category === cat.id ? 'none' : '1px solid var(--border-color)',
            }}
          >
            {cat.icon}
            {cat.label}
          </button>
        ))}
      </div>

      <motion.div 
        className="glass search-container"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        style={{ maxWidth: '1000px', display: 'flex', flexDirection: 'column', gap: '1rem', padding: '1.5rem' }}
      >
        <div style={{ display: 'flex', gap: '1rem', width: '100%' }}>
          <div style={{ position: 'relative', flex: 2 }}>
            <input 
              type="text" 
              placeholder={`Search for ${category.toLowerCase()} (e.g. "Software agencies" or "Luxury hotels")`}
              value={requirement}
              onChange={(e) => setRequirement(e.target.value)}
              style={{ width: '100%', height: '50px' }}
            />
          </div>
          <div style={{ position: 'relative', flex: 1 }}>
            <input 
              type="text" 
              placeholder="City/Region (Optional)" 
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              style={{ width: '100%', height: '50px' }}
            />
          </div>
          <div style={{ position: 'relative', flex: 1, minWidth: '150px' }}>
            <select 
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              style={{ 
                width: '100%', 
                height: '50px', 
                background: 'rgba(15, 23, 42, 0.6)', 
                border: '1px solid var(--border-color)', 
                color: 'white', 
                padding: '0 1rem', 
                borderRadius: '0.6rem',
                appearance: 'none',
              }}
            >
              <option value="ddgs">Free Organic (DDG)</option>
              <option value="serpapi">Google Maps (SerpApi)</option>
            </select>
            <div style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--text-muted)' }}>
              ▼
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', marginRight: '0.5rem' }}>
               Quick Regions:
            </span>
            {HIGH_VALUE_REGIONS.map(reg => (
              <button
                key={reg}
                onClick={() => setLocation(reg)}
                style={{
                  padding: '4px 10px',
                  fontSize: '0.7rem',
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '1rem',
                  color: location === reg ? 'var(--primary)' : 'var(--text-muted)'
                }}
              >
                {reg}
              </button>
            ))}
          </div>
          
          <button 
            onClick={handleSearch} 
            disabled={loading}
            style={{ padding: '0 2rem', height: '50px' }}
          >
            {loading ? <Loader2 className="loading-spinner" /> : <Search size={20} />}
            {loading ? (refining ? 'AI Refining...' : 'Finding Leads...') : 'Launch Scraper'}
          </button>
        </div>
      </motion.div>

      {leads.length > 0 && (
        <div className="tools-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <p className="subtitle" style={{ margin: 0 }}>Found {leads.length} Potential Leads</p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="export-btn" onClick={() => setExportModal(true)}>
              <FileSpreadsheet size={16} /> Google Sheets
            </button>
            <button className="export-btn" style={{ background: '#3b82f6' }} onClick={exportToCSV}>
              <FileText size={16} /> CSV
            </button>
            <button className="export-btn" style={{ background: '#6366f1' }} onClick={exportToJSON}>
              <FileJson size={16} /> JSON
            </button>
          </div>
        </div>
      )}

      <div className="leads-grid" style={{ marginTop: '1.5rem' }}>
        <AnimatePresence>
          {leads.map((lead, idx) => (
            <motion.div 
              key={lead.place_id || idx}
              className="glass lead-card"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.05 }}
              layout
            >
              <div className="lead-header">
                <h3 className="lead-title">{lead.title}</h3>
                <div className="lead-rating">
                  <Star size={14} fill="#fbbf24" strokeWidth={0} />
                  {lead.rating || 'N/A'}
                </div>
              </div>
              
              <div className="lead-info">
                <MapPin size={16} />
                <span>{lead.address || 'Location Hidden'}</span>
              </div>
              
              {lead.phone && (
                <div className="lead-info">
                  <Phone size={16} />
                  <span>{lead.phone}</span>
                </div>
              )}

              <div className="lead-links">
                {lead.website ? (
                  <a href={lead.website} target="_blank" rel="noopener noreferrer" className="lead-link">
                    <Globe size={14} style={{ marginRight: 4 }} />
                    View Website
                  </a>
                ) : (
                  <span style={{ fontSize: '0.85rem', color: 'rgba(239, 68, 68, 0.7)' }}>No Website</span>
                )}
                <a 
                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(lead.title + ' ' + (lead.address || ''))}`} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="lead-link"
                >
                  <ExternalLink size={14} style={{ marginRight: 4 }} />
                  Maps
                </a>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {leads.length === 0 && !loading && (
        <motion.div 
          style={{ textAlign: 'center', marginTop: '6rem', opacity: 0.4 }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.4 }}
        >
          <Briefcase size={64} style={{ marginBottom: '1.5rem', color: 'var(--primary)' }} />
          <h2 style={{ fontSize: '1.2rem' }}>Start Prospecting</h2>
          <p>Target the high-currency markets for maximum agency growth.</p>
        </motion.div>
      )}

      {/* Google Sheets Modal */}
      <AnimatePresence>
        {exportModal && (
          <div className="modal-overlay">
            <motion.div 
              className="glass modal-content"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem', alignItems: 'center' }}>
                <h2 className="modal-title" style={{ margin: 0, fontSize: '1.25rem' }}>Cloud Sync: Google Sheets</h2>
                <X style={{ cursor: 'pointer', color: 'var(--text-muted)' }} onClick={() => setExportModal(false)} />
              </div>
              
              <form onSubmit={handleGoogleSheetsExport}>
                <div className="input-group">
                  <label>Share spreadsheet with service account and paste ID:</label>
                  <input 
                    type="text" 
                    placeholder="Spreadsheet ID" 
                    value={sheetId}
                    onChange={(e) => setSheetId(e.target.value)}
                    required
                  />
                </div>
                
                {exportStatus && (
                  <p style={{ color: 'var(--accent)', marginBottom: '1rem', textAlign: 'center', fontWeight: 'bold' }}>{exportStatus}</p>
                )}

                <button 
                  type="submit" 
                  className="export-btn" 
                  style={{ width: '100%', height: '50px' }}
                  disabled={exportLoading}
                >
                  {exportLoading ? <Loader2 className="loading-spinner" /> : 'Start Cloud Sync'}
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <footer style={{ marginTop: '6rem', paddingBottom: '3rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
         AI Scraper &bull; Multiple Export Formats Enabled
      </footer>
    </div>
  );
};

export default App;
