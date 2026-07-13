/**
 * Application root: router + auth guard.
 *
 * Routes:
 * - /login     -> Login page (public)
 * - /register  -> Register page (public)
 * - /          -> Home dashboard (protected, requires valid token)
 */
import React, {useState, useEffect, useCallback} from 'react';
import {BrowserRouter, Routes, Route, Navigate, useLocation} from 'react-router-dom';
import {Spin} from 'antd';
import {getToken, clearToken, getCurrentUser} from '@/api';
import type {User} from '@/types';
import Layout from '@/components/Layout';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import Home from '@/pages/Home';

type ProtectedChildren = React.ReactNode | ((user: User) => React.ReactNode);

interface ProtectedRouteProps {
    children: ProtectedChildren;
}

/** Auth guard: validates token via /api/auth/me before rendering children */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({children}) => {
    const location = useLocation();
    const [loading, setLoading] = useState(true);
    const [valid, setValid] = useState(false);
    const [user, setUser] = useState<User | null>(null);

    const checkAuth = useCallback(async () => {
        const token = getToken();
        if (!token) {
            setValid(false);
            setLoading(false);
            return;
        }

        try {
            const response = await getCurrentUser();
            setUser(response.data);
            setValid(true);
        } catch {
            clearToken();
            setValid(false);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        checkAuth();
    }, [checkAuth]);

    if (loading) {
        return (
            <Layout>
                <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#f8fafc'}}>
                    <Spin size='large' tip='正在验证登录状态...' />
                </div>
            </Layout>
        );
    }

    if (!valid) {
        const returnUrl = encodeURIComponent(location.pathname + location.search);
        return <Navigate to={`/login?returnUrl=${returnUrl}`} replace />;
    }

    if (typeof children === 'function') {
        return <>{children(user!)}</>;
    }

    return <>{children as React.ReactNode}</>;
};

const App: React.FC = () => {
    return (
        <BrowserRouter>
            <Routes>
                <Route path='/login' element={<Login />} />
                <Route path='/register' element={<Register />} />
                <Route
                    path='/'
                    element={
                        <ProtectedRoute>{(user: User) => <Home user={user} />}</ProtectedRoute>
                    }
                />
                <Route path='*' element={<Navigate to='/' replace />} />
            </Routes>
        </BrowserRouter>
    );
};

export default App;
