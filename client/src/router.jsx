import { createBrowserRouter } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Analyze from './pages/Analyze';
import History from './pages/History';
import RoiTool from './pages/RoiTool';
import Leads from './pages/Leads';
import Login from './pages/Login';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Dashboard />,
  },
  {
    path: '/analyze',
    element: <Analyze />,
  },
  {
    path: '/history',
    element: <History />,
  },
  {
    path: '/roi',
    element: <RoiTool />,
  },
  {
    path: '/leads',
    element: <Leads />,
  },
  {
    path: '/login',
    element: <Login />,
  },
]);

export default router;
