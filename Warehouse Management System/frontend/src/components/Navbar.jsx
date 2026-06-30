import { AppBar, Toolbar, Typography, IconButton, Switch, Avatar, Menu, MenuItem } from '@mui/material'
import { useState } from 'react'
import { useThemeMode } from '../contexts/ThemeContext'
import { useNavigate } from 'react-router-dom'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'

export default function Navbar() {
  const { mode, toggleTheme } = useThemeMode()
  const navigate = useNavigate()
  const [anchorEl, setAnchorEl] = useState(null)
  const username = localStorage.getItem('username') || 'User'

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('username')
    navigate('/login')
    setAnchorEl(null)
  }

  return (
    <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Warehouse Control
        </Typography>
        <IconButton onClick={toggleTheme} sx={{ color: 'text.secondary' }}>
          {mode === 'dark' ? <DarkModeIcon /> : <LightModeIcon />}
        </IconButton>
        <Switch checked={mode === 'dark'} onChange={toggleTheme} size="small" />
        <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} sx={{ ml: 1 }}>
          <Avatar sx={{ width: 32, height: 32 }}>
            {username.charAt(0).toUpperCase()}
          </Avatar>
        </IconButton>
        <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
          <MenuItem disabled>{username}</MenuItem>
          <MenuItem onClick={handleLogout}>Logout</MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  )
}
