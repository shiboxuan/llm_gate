/**
 * Simplified standalone Layout for the LLM Gate frontend.
 *
 * Provides antd ConfigProvider theming (light/dark) and renders children.
 * Unlike the original Layout (coupled to the main-site router/configStore/auth),
 * this version has zero external coupling. The Home page supplies its own
 * sidebar + header inside this themed wrapper.
 */
import React, {useEffect} from 'react';
import {ConfigProvider, theme as antdTheme} from 'antd';
import themeStore from '@/store';

interface LayoutProps {
    children: React.ReactNode;
    /** Override the theme mode; falls back to the global themeStore */
    themeMode?: 'light' | 'dark';
}

const Layout: React.FC<LayoutProps> = ({children, themeMode}) => {
    const {mode} = themeStore();
    const effectiveMode = themeMode ?? mode;
    const isDark = effectiveMode === 'dark';

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', effectiveMode);
    }, [effectiveMode]);

    return (
        <ConfigProvider
            theme={{
                algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
                token: {
                    colorPrimary: '#722ed1',
                    borderRadius: 6,
                    fontSize: 14
                }
            }}
        >
            {children}
        </ConfigProvider>
    );
};

export default Layout;
