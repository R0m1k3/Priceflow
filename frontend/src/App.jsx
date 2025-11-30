import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import Search from '@/pages/Search'
import MultiSearch from '@/pages/MultiSearch'
import AmazonSearch from '@/pages/AmazonSearch'
import Catalogues from '@/pages/Catalogues'
import Login from '@/pages/Login'
import Admin from '@/pages/Admin'
import { useTheme } from '@/hooks/use-theme'
import { AuthProvider, useAuth } from '@/hooks/use-auth'

// Protected route wrapper
function ProtectedRoute({ children, adminOnly = false }) {
    const { isAuthenticated, isAdmin, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    if (adminOnly && !isAdmin) {
        return <Navigate to="/" replace />;
    }

    return children;
}

// Public route that redirects to home if already logged in
function PublicRoute({ children }) {
    const { isAuthenticated, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (isAuthenticated) {
        return <Navigate to="/" replace />;
    }

    return children;
}

function AppRoutes() {
    const { theme, toggleTheme } = useTheme();
    const { isAuthenticated } = useAuth();

    return (
        <>
            <Toaster position="bottom-right" theme={theme} />
            <Routes>
                <Route
                    path="/login"
                    element={
                        <PublicRoute>
                            <Login />
                        </PublicRoute>
                    }
                />
                <Route
                    path="/*"
                    element={
                        <ProtectedRoute>
                            <Layout theme={theme} toggleTheme={toggleTheme}>
                                <Routes>
                                    <Route path="/" element={<Dashboard />} />
                                    <Route path="/search" element={<Search />} />
                                    <Route path="/compare" element={<MultiSearch />} />
                                    <Route path="/amazon" element={<AmazonSearch />} />
                                    <Route path="/catalogues" element={<Catalogues />} />
                                    <Route
                                        path="/admin"
                                        element={
                                            <ProtectedRoute adminOnly>
                                                <Admin />
                                            </ProtectedRoute>
                                        }
                                    />
                                </Routes>
                            </Layout>
                        </ProtectedRoute>
                    }
                />
            </Routes>
        </>
    );
}

export default function App() {
    return (
        <Router>
            <AuthProvider>
                <AppRoutes />
            </AuthProvider>
        </Router>
    );
}
