import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const API_URL = '/api/auth';

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    // Check for existing token on mount
    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            // Verify token is still valid
            axios.get(`${API_URL}/me`, {
                headers: { Authorization: `Bearer ${token}` }
            })
            .then(response => {
                setUser({
                    ...response.data,
                    token
                });
            })
            .catch(() => {
                // Token invalid, clear it
                localStorage.removeItem('token');
            })
            .finally(() => {
                setLoading(false);
            });
        } else {
            setLoading(false);
        }
    }, []);

    const login = async (username, password) => {
        const response = await axios.post(`${API_URL}/login`, {
            username,
            password
        });

        const { token, username: userName, is_admin } = response.data;
        localStorage.setItem('token', token);

        setUser({
            username: userName,
            is_admin,
            token
        });

        return response.data;
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
    };

    const changePassword = async (currentPassword, newPassword) => {
        const token = localStorage.getItem('token');
        await axios.post(`${API_URL}/change-password`, {
            current_password: currentPassword,
            new_password: newPassword
        }, {
            headers: { Authorization: `Bearer ${token}` }
        });
    };

    // Helper function to get auth headers for API calls
    const getAuthHeaders = () => {
        const token = localStorage.getItem('token');
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    const value = {
        user,
        loading,
        login,
        logout,
        changePassword,
        getAuthHeaders,
        isAuthenticated: !!user,
        isAdmin: user?.is_admin || false
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
