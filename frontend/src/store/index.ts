import {create} from 'zustand';
import {createJSONStorage, persist} from 'zustand/middleware';

export type ThemeMode = 'light' | 'dark';

export interface ThemeState {
    mode: ThemeMode;
    setMode: (mode: ThemeMode) => void;
    toggleMode: () => void;
}

const themeStore = create<ThemeState>()(
    persist(
        (set, get) => ({
            mode: 'light',
            setMode: (mode) => set({mode}),
            toggleMode: () => set({mode: get().mode === 'light' ? 'dark' : 'light'})
        }),
        {
            name: 'llm-gate-theme-storage',
            storage: createJSONStorage(() => localStorage)
        }
    )
);

export default themeStore;
