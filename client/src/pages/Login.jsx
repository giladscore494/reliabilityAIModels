import { useNavigate } from 'react-router-dom';
import { useGoogleLogin } from '@react-oauth/google';
import { useState } from 'react';

export default function Login() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  const login = useGoogleLogin({
    onSuccess: (tokenResponse) => {
      // Store the token
      localStorage.setItem('google_token', tokenResponse.access_token);
      // Navigate to dashboard
      navigate('/');
    },
    onError: () => {
      setError('Login failed. Please try again.');
    },
  });

  return (
    <div className="container" style={{ maxWidth: '400px', marginTop: '100px' }}>
      <h1 style={{ textAlign: 'center', marginBottom: '2rem' }}>🚗 Car Reliability Analyzer</h1>
      <div style={{ textAlign: 'center' }}>
        <button 
          onClick={() => login()}
          style={{ 
            padding: '1rem 2rem', 
            fontSize: '1.1rem',
            backgroundColor: '#4285f4',
            color: 'white',
            border: 'none'
          }}
        >
          Sign in with Google
        </button>
        {error && <p style={{ color: 'red', marginTop: '1rem' }}>{error}</p>}
        <p style={{ marginTop: '2rem', fontSize: '0.9rem', opacity: 0.7 }}>
          Sign in to access analysis history and advanced features
        </p>
      </div>
    </div>
  );
}
