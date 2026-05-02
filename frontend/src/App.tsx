import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import RequireAuth from './auth/RequireAuth';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Trades from './pages/Trades';
import CalendarPage from './pages/Calendar';
import Analytics from './pages/Analytics';
import Login from './pages/Login';
import Register from './pages/Register';
import Settings from './pages/Settings';

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="trades" element={<Trades />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
