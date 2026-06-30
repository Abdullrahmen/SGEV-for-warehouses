import { createContext, useContext, useState, useMemo } from 'react'
import { ThemeProvider, createTheme, CssBaseline, GlobalStyles } from '@mui/material'

const ThemeContext = createContext()

export function ThemeContextProvider({ children }) {
  const [mode, setMode] = useState(() => {
    return localStorage.getItem('theme_mode') || 'dark'
  })

  const toggleTheme = () => {
    setMode((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      localStorage.setItem('theme_mode', next)
      return next
    })
  }

  const theme = useMemo(() => createTheme({
    palette: {
      mode,
      ...(mode === 'dark'
        ? {
            background: { default: '#1e1e2e', paper: '#313244' },
            primary: { main: '#89b4fa' },
            secondary: { main: '#cba6f7' },
            text: { primary: '#cdd6f4', secondary: '#a6adc8' },
            divider: '#45475a',
            error: { main: '#f38ba8' },
            warning: { main: '#fab387' },
            success: { main: '#a6e3a1' },
            info: { main: '#89dceb' },
            action: {
              active: '#89b4fa',
              hover: 'rgba(137, 180, 250, 0.08)',
              selected: 'rgba(137, 180, 250, 0.16)',
            },
            charcoal: '#181825',
          }
        : {
            background: { default: '#eff1f5', paper: '#e6e9ef' },
            primary: { main: '#1e66f5' },
            secondary: { main: '#8839ef' },
            text: { primary: '#4c4f69', secondary: '#6c6f85' },
            divider: '#ccd0da',
            error: { main: '#d20f39' },
            warning: { main: '#fe640b' },
            success: { main: '#40a02b' },
            info: { main: '#04a5e5' },
          }),
    },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    },
    shape: { borderRadius: 8 },
    components: {
      MuiCard: {
        styleOverrides: {
          root: ({ theme }) => ({
            background: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: 'none',
          }),
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
          },
          contained: {
            boxShadow: 'none',
            '&:hover': { boxShadow: 'none' },
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: ({ theme }) => ({
            ...(theme.palette.mode === 'dark' && {
              backgroundColor: '#181825',
              borderBottom: '1px solid #313244',
              boxShadow: 'none',
            }),
          }),
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: ({ theme }) => ({
            ...(theme.palette.mode === 'dark' && {
              backgroundColor: '#181825',
              borderRight: '1px solid #313244',
            }),
          }),
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: ({ theme }) => ({
            border: 'none',
            '--DataGrid-rowBorderColor': theme.palette.divider,
            borderRadius: 8,
            '& .MuiDataGrid-cell:focus': { outline: 'none' },
            '& .MuiDataGrid-cell:focus-within': { outline: 'none' },
            '& .MuiDataGrid-columnHeader:focus': { outline: 'none' },
            '& .MuiDataGrid-columnHeader:focus-within': { outline: 'none' },
          }),
          columnHeaders: ({ theme }) => ({
            borderBottom: `1px solid ${theme.palette.divider}`,
          }),
          row: ({ theme }) => ({
            '&:hover': { background: theme.palette.action.hover },
          }),
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: ({ theme }) => ({
            '&.MuiInputLabel-outlined.MuiInputLabel-shrink': {
              background: theme.palette.background.paper,
              padding: '0 6px',
            },
          }),
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: ({ theme }) => ({
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: theme.palette.divider,
            },
          }),
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 500,
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: ({ theme }) => ({
            borderRadius: 6,
            '&.Mui-selected': {
              backgroundColor: theme.palette.action.selected,
              '&:hover': { backgroundColor: theme.palette.action.selected },
            },
          }),
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: ({ theme }) => ({
            ...(theme.palette.mode === 'dark' && {
              backgroundImage: 'none',
              border: '1px solid #313244',
            }),
          }),
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: ({ theme }) => ({
            ...(theme.palette.mode === 'dark' && {
              backgroundImage: 'none',
              border: '1px solid #313244',
            }),
          }),
        },
      },
    },
  }), [mode])

  return (
    <ThemeContext.Provider value={{ mode, toggleTheme }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <GlobalStyles styles={(theme) => ({
          '*': {
            scrollbarWidth: 'thin',
            scrollbarColor: theme.palette.mode === 'dark'
              ? '#45475a transparent'
              : '#ccd0da transparent',
          },
          body: {
            transition: 'background-color 0.3s, color 0.3s',
          },
          ...(theme.palette.mode === 'dark' && {
            '*': {
              transition: 'background-color 0.2s, border-color 0.2s',
            },
            'div.MuiDataGrid-root': {
              '--DataGrid-t-color-background-base': '#1e1e2e',
              '--DataGrid-t-header-background-base': '#181825',
            },
          }),
          '::selection': {
            backgroundColor: theme.palette.mode === 'dark'
              ? 'rgba(137, 180, 250, 0.3)'
              : 'rgba(30, 102, 245, 0.2)',
          },
          ':focus-visible': {
            outline: `2px solid ${theme.palette.primary.main}`,
            outlineOffset: 2,
          },
        })} />
        {children}
      </ThemeProvider>
    </ThemeContext.Provider>
  )
}

export const useThemeMode = () => useContext(ThemeContext)
