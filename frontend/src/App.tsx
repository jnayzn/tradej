import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Trades from './pages/Trades';
import CalendarPage from './pages/Calendar';
import Analytics from './pages/Analytics';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="trades" element={<Trades />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
