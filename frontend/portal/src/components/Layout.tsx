import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { LayoutDashboard, Key, HardDrive, FileText, Settings, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils'; // Will need to copy utils.ts

export default function Layout() {
    const { logout } = useAuth();
    const location = useLocation();

    const navigation = [
        { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
        { name: 'API Keys', href: '/keys', icon: Key },
        { name: 'Usage', href: '/usage', icon: HardDrive },
        { name: 'Jobs', href: '/jobs', icon: FileText },
        { name: 'Settings', href: '/settings', icon: Settings },
    ];

    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <div className="flex w-64 flex-col bg-white border-r">
                <div className="flex h-16 items-center px-6 text-xl font-bold text-indigo-600">
                    ParseFin
                </div>
                <div className="flex flex-1 flex-col overflow-y-auto">
                    <nav className="flex-1 space-y-1 px-2 py-4">
                        {navigation.map((item) => {
                            const isActive = location.pathname.startsWith(item.href);
                            return (
                                <Link
                                    key={item.name}
                                    to={item.href}
                                    className={cn(
                                        isActive ? 'bg-indigo-50 text-indigo-600' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                                        'group flex items-center rounded-md px-2 py-2 text-sm font-medium'
                                    )}
                                >
                                    <item.icon className={cn("mr-3 h-6 w-6 flex-shrink-0", isActive ? 'text-indigo-600' : 'text-gray-400')} />
                                    {item.name}
                                </Link>
                            );
                        })}
                    </nav>
                </div>
                <div className="border-t p-4">
                    <button
                        onClick={logout}
                        className="flex w-full items-center text-sm text-gray-600 hover:text-gray-900"
                    >
                        <LogOut className="mr-2 h-4 w-4" />
                        Sign out
                    </button>
                </div>
            </div>

            {/* Main content */}
            <div className="flex flex-1 flex-col overflow-hidden">
                <main className="flex-1 overflow-y-auto bg-gray-50 p-8">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
