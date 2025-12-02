import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LayoutDashboard, Search, TrendingUp, BookOpen, Menu, LogOut, Shield, ShoppingBag } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/use-auth';

const Layout = ({ children }) => {
    const { t } = useTranslation();
    const location = useLocation();
    const navigate = useNavigate();
    const { user, logout, isAdmin } = useAuth();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    // Main navigation items (without admin)
    const navItems = [
        { icon: LayoutDashboard, label: t('nav.dashboard'), path: '/' },
        { icon: Search, label: t('nav.search') || 'Recherche', path: '/search' },
        { icon: ShoppingBag, label: 'Amazon France', path: '/amazon' },
        { icon: TrendingUp, label: 'Comparateur', path: '/compare' },
        { icon: BookOpen, label: 'Catalogues', path: '/catalogues' },
    ];

    return (
        <div className="min-h-screen bg-background">
            {/* Desktop Sidebar */}
            <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r bg-white hidden md:block">
                <div className="flex h-full flex-col">
                    {/* Logo */}
                    <div className="flex h-16 items-center border-b px-6">
                        <Link to="/" className="flex items-center gap-3">
                            <img src="/logo.png" alt="PriceFlow" className="h-8 w-8" />
                            <span className="text-lg font-semibold text-foreground">
                                PriceFlow
                            </span>
                        </Link>
                    </div>

                    {/* Main Navigation */}
                    <nav className="flex-1 p-3 space-y-1">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            const isActive = location.pathname === item.path;
                            return (
                                <Link key={item.path} to={item.path}>
                                    <Button
                                        variant={isActive ? "secondary" : "ghost"}
                                        className={cn(
                                            "w-full justify-start gap-3 h-10 px-3",
                                            isActive && "bg-secondary font-medium"
                                        )}
                                    >
                                        <Icon className="h-4 w-4" />
                                        <span className="text-sm">{item.label}</span>
                                    </Button>
                                </Link>
                            );
                        })}
                    </nav>

                    {/* Bottom Section: Admin + User + Logout */}
                    <div className="border-t">
                        {/* Admin Button (separated) */}
                        {isAdmin && (
                            <div className="p-3 border-b">
                                <Link to="/admin">
                                    <Button
                                        variant={location.pathname === '/admin' ? "secondary" : "ghost"}
                                        className={cn(
                                            "w-full justify-start gap-3 h-10 px-3",
                                            location.pathname === '/admin' && "bg-secondary font-medium"
                                        )}
                                    >
                                        <Shield className="h-4 w-4" />
                                        <span className="text-sm">Administration</span>
                                    </Button>
                                </Link>
                            </div>
                        )}

                        {/* User Info */}
                        <div className="p-3 border-b">
                            <div className="px-3 py-2 text-xs text-muted-foreground">
                                <div className="font-medium text-foreground text-sm">{user?.username}</div>
                                {isAdmin && (
                                    <div className="mt-1 inline-block text-xs bg-secondary px-2 py-0.5 rounded">
                                        Administrateur
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Logout */}
                        <div className="p-3">
                            <Button
                                variant="ghost"
                                onClick={handleLogout}
                                className="w-full justify-start gap-3 h-10 px-3 text-muted-foreground hover:text-foreground"
                            >
                                <LogOut className="h-4 w-4" />
                                <span className="text-sm">Déconnexion</span>
                            </Button>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Mobile Header */}
            <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-white px-4 md:hidden">
                <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
                    <SheetTrigger asChild>
                        <Button variant="ghost" size="icon">
                            <Menu className="h-5 w-5" />
                        </Button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-64 p-0">
                        <div className="flex h-full flex-col">
                            {/* Mobile Logo */}
                            <div className="flex h-16 items-center border-b px-6">
                                <img src="/logo.png" alt="PriceFlow" className="h-8 w-8 mr-3" />
                                <span className="text-lg font-semibold">PriceFlow</span>
                            </div>

                            {/* Mobile Navigation */}
                            <nav className="flex-1 p-3 space-y-1">
                                {navItems.map((item) => {
                                    const Icon = item.icon;
                                    const isActive = location.pathname === item.path;
                                    return (
                                        <Link key={item.path} to={item.path} onClick={() => setMobileMenuOpen(false)}>
                                            <Button
                                                variant={isActive ? "secondary" : "ghost"}
                                                className={cn(
                                                    "w-full justify-start gap-3 h-10 px-3",
                                                    isActive && "bg-secondary font-medium"
                                                )}
                                            >
                                                <Icon className="h-4 w-4" />
                                                <span className="text-sm">{item.label}</span>
                                            </Button>
                                        </Link>
                                    );
                                })}
                            </nav>

                            {/* Mobile Bottom Section */}
                            <div className="border-t">
                                {isAdmin && (
                                    <div className="p-3 border-b">
                                        <Link to="/admin" onClick={() => setMobileMenuOpen(false)}>
                                            <Button
                                                variant={location.pathname === '/admin' ? "secondary" : "ghost"}
                                                className={cn(
                                                    "w-full justify-start gap-3 h-10 px-3",
                                                    location.pathname === '/admin' && "bg-secondary font-medium"
                                                )}
                                            >
                                                <Shield className="h-4 w-4" />
                                                <span className="text-sm">Administration</span>
                                            </Button>
                                        </Link>
                                    </div>
                                )}

                                <div className="p-3 border-b">
                                    <div className="px-3 py-2 text-xs text-muted-foreground">
                                        <div className="font-medium text-foreground text-sm">{user?.username}</div>
                                        {isAdmin && (
                                            <div className="mt-1 inline-block text-xs bg-secondary px-2 py-0.5 rounded">
                                                Administrateur
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="p-3">
                                    <Button
                                        variant="ghost"
                                        onClick={() => { handleLogout(); setMobileMenuOpen(false); }}
                                        className="w-full justify-start gap-3 h-10 px-3 text-muted-foreground hover:text-foreground"
                                    >
                                        <LogOut className="h-4 w-4" />
                                        <span className="text-sm">Déconnexion</span>
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </SheetContent>
                </Sheet>

                <Link to="/" className="flex items-center gap-2">
                    <img src="/logo.png" alt="PriceFlow" className="h-7 w-7" />
                    <span className="font-semibold">PriceFlow</span>
                </Link>
            </header>

            {/* Main Content */}
            <main className="md:pl-64">
                <div className="container max-w-7xl py-6 px-4">
                    {children}
                </div>
            </main>
        </div>
    );
};

export default Layout;
