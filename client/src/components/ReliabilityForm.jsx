import { useState } from 'react';
import { modelsDictFallback } from '../utils/modelsDictFallback';

export default function ReliabilityForm({ onSubmit, loading }) {
  const [formData, setFormData] = useState({
    make: '',
    model: '',
    sub_model: '',
    year: new Date().getFullYear(),
    fuel_type: 'בנזין',
    transmission: 'אוטומטית',
    mileage_range: '100,000 - 150,000 ק"מ',
    advanced_mode: false
  });

  const mileageRanges = [
    'עד 50,000 ק"מ',
    '50,000 - 100,000 ק"מ',
    '100,000 - 150,000 ק"מ',
    '150,000 - 200,000 ק"מ',
    '200,000+ ק"מ'
  ];

  const fuelTypes = ['בנזין', 'דיזל', 'היברידי', 'חשמלי', 'אחר'];
  const transmissions = ['אוטומטית', 'ידנית'];

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const makes = Object.keys(modelsDictFallback).sort();
  const models = formData.make ? modelsDictFallback[formData.make] || [] : [];

  return (
    <form onSubmit={handleSubmit} style={{ 
      background: '#1a1a1a', 
      padding: '2rem', 
      borderRadius: '8px' 
    }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Make / יצרן</label>
          <select
            name="make"
            value={formData.make}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          >
            <option value="">Select Make</option>
            {makes.map(make => (
              <option key={make} value={make}>{make}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Model / דגם</label>
          <select
            name="model"
            value={formData.model}
            onChange={handleChange}
            required
            disabled={!formData.make}
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          >
            <option value="">Select Model</option>
            {models.map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Sub-Model / תת-דגם (optional)</label>
          <input
            type="text"
            name="sub_model"
            value={formData.sub_model}
            onChange={handleChange}
            placeholder="e.g., האצ'בק"
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Year / שנה</label>
          <input
            type="number"
            name="year"
            value={formData.year}
            onChange={handleChange}
            min="1960"
            max={new Date().getFullYear()}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Fuel Type / סוג דלק</label>
          <select
            name="fuel_type"
            value={formData.fuel_type}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          >
            {fuelTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Transmission / גיר</label>
          <select
            name="transmission"
            value={formData.transmission}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          >
            {transmissions.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        <div style={{ gridColumn: '1 / -1' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>Mileage Range / טווח ק״מ</label>
          <select
            name="mileage_range"
            value={formData.mileage_range}
            onChange={handleChange}
            required
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #333', background: '#2a2a2a', color: 'white' }}
          >
            {mileageRanges.map(range => (
              <option key={range} value={range}>{range}</option>
            ))}
          </select>
        </div>
      </div>

      <button 
        type="submit" 
        disabled={loading}
        style={{ 
          width: '100%', 
          marginTop: '1.5rem',
          background: loading ? '#555' : '#646cff'
        }}
      >
        {loading ? 'Analyzing...' : '🔎 Analyze Reliability'}
      </button>
    </form>
  );
}
