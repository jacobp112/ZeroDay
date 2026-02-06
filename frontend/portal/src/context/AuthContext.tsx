import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '@/api/client';

interface User {
    tenant_id: string;
    organization_id: string;
    scope: string;
}

interface AuthContextType {
    user: User | null;
    login: (token: string) => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem('portal_token');
        if (token) {
            api.get('/portal/auth/me')
                .then((res) => setUser(res.data))
                .catch(() => {
                    localStorage.removeItem('portal_token');
                    setUser(null);
                })
                .finally(() => setIsLoading(false));
        } else {
            setIsLoading(false);
        }
    }, []);

    const login = (token: string) => {
        localStorage.setItem('portal_token', token);
        api.get('/portal/auth/me').then((res) => setUser(res.data));
    };

    const logout = () => {
        localStorage.removeItem('portal_token');
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error('useAuth must be used within AuthProvider');
    return context;
};
