export default function ChecksCard({ checks }) {
  const hasChecks = checks && checks.length > 0;

  if (!hasChecks) {
    return (
      <div style={{ 
        background: '#1a1a1a', 
        padding: '1.5rem', 
        borderRadius: '8px',
        border: '1px solid #333',
        textAlign: 'right'
      }}>
        <h3 style={{ marginBottom: '1rem' }}>🔬 בדיקות מומלצות</h3>
        <p style={{ opacity: 0.7 }}>אין המלצות בדיקה ספציפיות שמורות.</p>
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
      <h3 style={{ marginBottom: '1rem', textAlign: 'right' }}>🔬 בדיקות מומלצות במוסך</h3>
      <ul style={{ 
        listStyle: 'none', 
        padding: 0, 
        margin: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        textAlign: 'right'
      }}>
        {checks.map((check, idx) => (
          check && (
            <li key={idx} style={{ 
              padding: '0.7rem',
              background: '#2a2a2a',
              borderRadius: '4px',
              borderRight: '3px solid #44ff44',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.5rem',
              flexDirection: 'row-reverse'
            }}>
              <span style={{ 
                minWidth: '24px',
                height: '24px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#646cff',
                borderRadius: '50%',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                flexShrink: 0
              }}>
                {idx + 1}
              </span>
              <span style={{ flex: 1 }}>{check}</span>
            </li>
          )
        ))}
      </ul>
      <div style={{ 
        marginTop: '1rem',
        padding: '0.7rem',
        background: '#2a2a2a',
        borderRadius: '4px',
        fontSize: '0.85rem',
        opacity: 0.8,
        textAlign: 'right'
      }}>
        💡 <strong>טיפ:</strong> בצע את הבדיקות הללו לפני קניית הרכב או כחלק מתחזוקה שגרתית
      </div>
    </div>
  );
}
