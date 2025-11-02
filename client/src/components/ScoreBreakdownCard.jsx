export default function ScoreBreakdownCard({ breakdown }) {
  if (!breakdown) return null;

  const categories = [
    { key: 'engine_transmission_score', label: 'מנוע וגיר', icon: '⚙️' },
    { key: 'electrical_score', label: 'חשמל/אלקטרוניקה', icon: '⚡' },
    { key: 'suspension_brakes_score', label: 'מתלים/בלמים', icon: '🛞' },
    { key: 'maintenance_cost_score', label: 'עלות אחזקה', icon: '💰' },
    { key: 'satisfaction_score', label: 'שביעות רצון', icon: '😊' },
    { key: 'recalls_score', label: 'ריקולים', icon: '⚠️' }
  ];

  return (
    <div style={{ 
      background: '#1a1a1a', 
      padding: '1.5rem', 
      borderRadius: '8px',
      border: '1px solid #333'
    }}>
      <h3 style={{ marginBottom: '1rem', textAlign: 'right' }}>📊 פירוט ציון (1-10)</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
        {categories.map(({ key, label, icon }) => {
          const score = breakdown[key];
          const scoreNum = typeof score === 'number' ? score : parseInt(score) || 0;
          const percentage = (scoreNum / 10) * 100;
          
          return (
            <div key={key} style={{ textAlign: 'right' }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: '0.3rem'
              }}>
                <span style={{ fontWeight: 'bold', color: '#646cff' }}>
                  {scoreNum}/10
                </span>
                <span>{icon} {label}</span>
              </div>
              <div style={{ 
                width: '100%', 
                height: '8px', 
                background: '#2a2a2a', 
                borderRadius: '4px',
                overflow: 'hidden'
              }}>
                <div style={{ 
                  width: `${percentage}%`, 
                  height: '100%', 
                  background: scoreNum >= 8 ? '#44ff44' : scoreNum >= 6 ? '#ffaa00' : '#ff4444',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
