export default function CompetitorsCard({ competitors }) {
  const hasCompetitors = competitors && competitors.length > 0;

  if (!hasCompetitors) {
    return (
      <div style={{ 
        background: '#1a1a1a', 
        padding: '1.5rem', 
        borderRadius: '8px',
        border: '1px solid #333',
        textAlign: 'right'
      }}>
        <h3 style={{ marginBottom: '1rem' }}>🚗 מתחרים נפוצים</h3>
        <p style={{ opacity: 0.7 }}>אין נתוני מתחרים שמורים.</p>
      </div>
    );
  }

  return (
    <div style={{ 
      background: '#1a1a1a', 
      padding: '1.5rem', 
      borderRadius: '8px',
      border: '1px solid #333'
    }}>
      <h3 style={{ marginBottom: '1rem', textAlign: 'right' }}>🚗 מתחרים נפוצים</h3>
      <div style={{ 
        display: 'flex',
        flexDirection: 'column',
        gap: '0.8rem'
      }}>
        {competitors.map((comp, idx) => {
          if (!comp || typeof comp !== 'object') return null;
          
          const model = comp.model || '';
          const summary = comp.brief_summary || '';
          
          if (!model) return null;
          
          return (
            <div key={idx} style={{ 
              padding: '1rem',
              background: '#2a2a2a',
              borderRadius: '4px',
              border: '1px solid #333',
              transition: 'border-color 0.3s',
              cursor: 'default'
            }}
            onMouseEnter={(e) => e.currentTarget.style.borderColor = '#646cff'}
            onMouseLeave={(e) => e.currentTarget.style.borderColor = '#333'}
            >
              <div style={{ 
                fontWeight: 'bold',
                fontSize: '1.05rem',
                marginBottom: '0.5rem',
                color: '#646cff',
                textAlign: 'right'
              }}>
                {model}
              </div>
              {summary && (
                <div style={{ 
                  fontSize: '0.9rem',
                  opacity: 0.85,
                  lineHeight: '1.5',
                  textAlign: 'right'
                }}>
                  {summary}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{ 
        marginTop: '1rem',
        padding: '0.7rem',
        background: '#2a2a2a',
        borderRadius: '4px',
        fontSize: '0.85rem',
        opacity: 0.8,
        textAlign: 'right'
      }}>
        ℹ️ רכבים מתחרים באותה קטגוריה ותחום מחירים
      </div>
    </div>
  );
}
