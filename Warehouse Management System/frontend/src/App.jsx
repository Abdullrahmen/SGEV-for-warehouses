import { Routes, Route } from 'react-router-dom'
import { Box, Toolbar } from '@mui/material'
import { ThemeContextProvider } from './contexts/ThemeContext'
import { WebSocketContextProvider } from './contexts/WebSocketContext'
import { RobotContextProvider } from './contexts/RobotContext'
import Navbar from './components/Navbar'
import Sidebar, { DRAWER_WIDTH } from './components/Sidebar'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import LiveMap from './pages/LiveMap'
import ManualControl from './pages/ManualControl'
import Inventory from './pages/Inventory'
import Orders from './pages/Orders'

function AppLayout({ children }) {
  return (
    <Box sx={{ display: 'flex' }}>
      <Navbar />
      <Sidebar />
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  )
}

export default function App() {
  return (
    <ThemeContextProvider>
      <WebSocketContextProvider>
        <RobotContextProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={
              <ProtectedRoute>
                <AppLayout>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/live-map" element={<LiveMap />} />
                    <Route path="/manual-control" element={<ManualControl />} />
                    <Route path="/inventory" element={<Inventory />} />
                    <Route path="/orders" element={<Orders />} />
                  </Routes>
                </AppLayout>
              </ProtectedRoute>
            } />
          </Routes>
        </RobotContextProvider>
      </WebSocketContextProvider>
    </ThemeContextProvider>
  )
}
