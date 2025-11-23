import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
    Users, UserPlus, Trash2, Key, Shield, ShieldOff,
    Settings as SettingsIcon, Cpu, Clock, Bell, Globe,
    ChevronDown, ChevronUp, RefreshCw, RotateCcw, Edit2,
    Sparkles, Eye, Code, Brain, DollarSign, Filter,
    TrendingDown, CheckCircle2, Package
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/use-auth';

const API_URL = '/api';

const categoryIcons = {
    chat: Sparkles,
    vision: Eye,
    code: Code,
    reasoning: Brain,
    free: DollarSign
};

export default function Admin() {
    const navigate = useNavigate();
    const { user, getAuthHeaders, isAdmin, changePassword } = useAuth();
    const [activeTab, setActiveTab] = useState('users');

    // User management state
    const [users, setUsers] = useState([]);
    const [newUser, setNewUser] = useState({ username: '', password: '', is_admin: false });
    const [passwordChange, setPasswordChange] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
    const [adminPasswordChange, setAdminPasswordChange] = useState({ userId: null, newPassword: '' });

    // Settings state (from Settings.jsx)
    const [profiles, setProfiles] = useState([]);
    const [jobConfig, setJobConfig] = useState({ refresh_interval_minutes: 60, next_run: null, running: false });
    const [config, setConfig] = useState({
        ai_provider: 'ollama',
        ai_model: 'moondream',
        ai_api_key: '',
        ai_api_base: 'http://ollama:11434',
        ai_temperature: 0.1,
        ai_max_tokens: 300,
        confidence_threshold_price: 0.5,
        confidence_threshold_stock: 0.5,
        enable_json_repair: true,
        smart_scroll_enabled: false,
        smart_scroll_pixels: 350,
        text_context_enabled: false,
        text_context_length: 5000,
        scraper_timeout: 90000
    });
    const [newProfile, setNewProfile] = useState({
        name: '',
        apprise_url: '',
        check_interval_minutes: 60,
        notify_on_price_drop: true,
        notify_on_target_price: true,
        price_drop_threshold_percent: 10,
        notify_on_stock_change: true
    });
    const [editingProfileId, setEditingProfileId] = useState(null);
    const [showAdvancedAI, setShowAdvancedAI] = useState(false);
    const [searchSites, setSearchSites] = useState([]);
    const [resettingSites, setResettingSites] = useState(false);
    const [openrouterModels, setOpenrouterModels] = useState([]);
    const [openrouterLoading, setOpenrouterLoading] = useState(false);
    const [openrouterCategory, setOpenrouterCategory] = useState('all');
    const [openrouterCategories] = useState([
        { id: 'all', name: 'Tous', description: 'Tous les modèles' },
        { id: 'chat', name: 'Chat', description: 'Conversation générale' },
        { id: 'vision', name: 'Vision', description: 'Analyse d\'images' },
        { id: 'code', name: 'Code', description: 'Programmation' },
        { id: 'reasoning', name: 'Raisonnement', description: 'Raisonnement avancé' },
        { id: 'free', name: 'Gratuit', description: 'Modèles gratuits' }
    ]);

    useEffect(() => {
        if (!isAdmin) {
            navigate('/');
            return;
        }
        fetchAll();
    }, [isAdmin, navigate]);

    useEffect(() => {
        if (config.ai_provider === 'openrouter') {
            fetchOpenRouterModels();
        }
    }, [config.ai_provider, openrouterCategory]);

    const fetchAll = async () => {
        try {
            const headers = getAuthHeaders();
            const [usersRes, profilesRes, settingsRes, jobRes, sitesRes] = await Promise.all([
                axios.get(`${API_URL}/auth/users`, { headers }),
                axios.get(`${API_URL}/notification-profiles`),
                axios.get(`${API_URL}/settings`),
                axios.get(`${API_URL}/jobs/config`),
                axios.get(`${API_URL}/search-sites`)
            ]);

            setUsers(usersRes.data);
            setProfiles(profilesRes.data);
            setJobConfig(jobRes.data);
            setSearchSites(sitesRes.data);

            const settingsMap = {};
            settingsRes.data.forEach(s => settingsMap[s.key] = s.value);
            setConfig({
                ai_provider: settingsMap['ai_provider'] || 'ollama',
                ai_model: settingsMap['ai_model'] || 'moondream',
                ai_api_key: settingsMap['ai_api_key'] || '',
                ai_api_base: settingsMap['ai_api_base'] || 'http://ollama:11434',
                ai_temperature: parseFloat(settingsMap['ai_temperature'] || '0.1'),
                ai_max_tokens: parseInt(settingsMap['ai_max_tokens'] || '300'),
                confidence_threshold_price: parseFloat(settingsMap['confidence_threshold_price'] || '0.5'),
                confidence_threshold_stock: parseFloat(settingsMap['confidence_threshold_stock'] || '0.5'),
                enable_json_repair: settingsMap['enable_json_repair'] !== 'false',
                smart_scroll_enabled: settingsMap['smart_scroll_enabled'] === 'true',
                smart_scroll_pixels: parseInt(settingsMap['smart_scroll_pixels'] || '350'),
                text_context_enabled: settingsMap['text_context_enabled'] === 'true',
                text_context_length: parseInt(settingsMap['text_context_length'] || '5000'),
                scraper_timeout: parseInt(settingsMap['scraper_timeout'] || '90000')
            });
        } catch (error) {
            console.error('Error fetching data:', error);
            toast.error('Erreur lors du chargement des données');
        }
    };

    // User management functions
    const handleCreateUser = async (e) => {
        e.preventDefault();
        if (!newUser.username.trim() || !newUser.password) {
            toast.error('Veuillez remplir tous les champs');
            return;
        }
        try {
            await axios.post(`${API_URL}/auth/users`, newUser, { headers: getAuthHeaders() });
            toast.success('Utilisateur créé');
            setNewUser({ username: '', password: '', is_admin: false });
            fetchAll();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erreur lors de la création');
        }
    };

    const handleDeleteUser = async (userId) => {
        if (!confirm('Êtes-vous sûr de vouloir supprimer cet utilisateur ?')) return;
        try {
            await axios.delete(`${API_URL}/auth/users/${userId}`, { headers: getAuthHeaders() });
            toast.success('Utilisateur supprimé');
            fetchAll();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erreur lors de la suppression');
        }
    };

    const handleToggleUserActive = async (userId) => {
        try {
            await axios.put(`${API_URL}/auth/users/${userId}/toggle-active`, {}, { headers: getAuthHeaders() });
            toast.success('Statut modifié');
            fetchAll();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erreur lors de la modification');
        }
    };

    const handleChangeMyPassword = async (e) => {
        e.preventDefault();
        if (passwordChange.newPassword !== passwordChange.confirmPassword) {
            toast.error('Les mots de passe ne correspondent pas');
            return;
        }
        try {
            await changePassword(passwordChange.currentPassword, passwordChange.newPassword);
            toast.success('Mot de passe modifié');
            setPasswordChange({ currentPassword: '', newPassword: '', confirmPassword: '' });
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erreur lors du changement de mot de passe');
        }
    };

    const handleAdminChangePassword = async (e) => {
        e.preventDefault();
        if (!adminPasswordChange.userId || !adminPasswordChange.newPassword) return;
        try {
            await axios.put(
                `${API_URL}/auth/users/${adminPasswordChange.userId}/password`,
                { new_password: adminPasswordChange.newPassword },
                { headers: getAuthHeaders() }
            );
            toast.success('Mot de passe modifié');
            setAdminPasswordChange({ userId: null, newPassword: '' });
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erreur lors du changement de mot de passe');
        }
    };

    // Settings functions
    const updateSetting = async (key, value) => {
        try {
            await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
            setConfig(prev => ({ ...prev, [key]: value }));
            toast.success('Paramètre mis à jour');
        } catch (error) {
            toast.error('Erreur lors de la mise à jour');
        }
    };

    const fetchOpenRouterModels = async () => {
        setOpenrouterLoading(true);
        try {
            const params = new URLSearchParams();
            if (config.ai_api_key) params.append('api_key', config.ai_api_key);
            if (openrouterCategory && openrouterCategory !== 'all') params.append('category', openrouterCategory);
            const response = await axios.get(`${API_URL}/openrouter/models?${params.toString()}`);
            setOpenrouterModels(response.data.models || []);
        } catch (error) {
            console.error('Erreur chargement modèles OpenRouter:', error);
        } finally {
            setOpenrouterLoading(false);
        }
    };

    const formatPrice = (pricePerToken) => {
        if (!pricePerToken || pricePerToken === 0) return 'Gratuit';
        const pricePerMillion = pricePerToken * 1000000;
        if (pricePerMillion < 0.01) return `$${pricePerMillion.toFixed(4)}/1M`;
        if (pricePerMillion < 1) return `$${pricePerMillion.toFixed(3)}/1M`;
        return `$${pricePerMillion.toFixed(2)}/1M`;
    };

    const updateJobConfig = async () => {
        try {
            await axios.post(`${API_URL}/jobs/config`, {
                key: 'refresh_interval_minutes',
                value: jobConfig.refresh_interval_minutes.toString()
            });
            toast.success('Configuration du job mise à jour');
            fetchAll();
        } catch (error) {
            toast.error('Erreur lors de la mise à jour');
        }
    };

    // Profile functions
    const handleProfileSubmit = async (e) => {
        e.preventDefault();
        try {
            if (editingProfileId) {
                await axios.put(`${API_URL}/notification-profiles/${editingProfileId}`, newProfile);
                toast.success('Profil mis à jour');
            } else {
                await axios.post(`${API_URL}/notification-profiles`, newProfile);
                toast.success('Profil créé');
            }
            setNewProfile({
                name: '', apprise_url: '', check_interval_minutes: 60,
                notify_on_price_drop: true, notify_on_target_price: true,
                price_drop_threshold_percent: 10, notify_on_stock_change: true
            });
            setEditingProfileId(null);
            fetchAll();
        } catch (error) {
            toast.error('Erreur lors de l\'enregistrement');
        }
    };

    const editProfile = (profile) => {
        setNewProfile({
            name: profile.name, apprise_url: profile.apprise_url,
            check_interval_minutes: profile.check_interval_minutes,
            notify_on_price_drop: profile.notify_on_price_drop,
            notify_on_target_price: profile.notify_on_target_price,
            price_drop_threshold_percent: profile.price_drop_threshold_percent,
            notify_on_stock_change: profile.notify_on_stock_change
        });
        setEditingProfileId(profile.id);
    };

    const cancelEdit = () => {
        setNewProfile({
            name: '', apprise_url: '', check_interval_minutes: 60,
            notify_on_price_drop: true, notify_on_target_price: true,
            price_drop_threshold_percent: 10, notify_on_stock_change: true
        });
        setEditingProfileId(null);
    };

    const deleteProfile = async (id) => {
        if (confirm('Êtes-vous sûr de vouloir supprimer ce profil ?')) {
            try {
                await axios.delete(`${API_URL}/notification-profiles/${id}`);
                toast.success('Profil supprimé');
                if (editingProfileId === id) cancelEdit();
                fetchAll();
            } catch (error) {
                toast.error('Erreur lors de la suppression');
            }
        }
    };

    // Site functions
    const toggleSiteActive = async (site) => {
        try {
            await axios.put(`${API_URL}/search-sites/${site.id}`, { is_active: !site.is_active });
            fetchAll();
        } catch (error) {
            toast.error('Erreur lors de la mise à jour');
        }
    };

    const resetSitesToDefaults = async () => {
        if (!confirm('Êtes-vous sûr de vouloir réinitialiser tous les sites ?')) return;
        setResettingSites(true);
        try {
            const response = await axios.post(`${API_URL}/search-sites/reset`);
            toast.success(response.data.message);
            fetchAll();
        } catch (error) {
            toast.error('Erreur lors de la réinitialisation');
        } finally {
            setResettingSites(false);
        }
    };

    const tabs = [
        { id: 'users', label: 'Utilisateurs', icon: Users },
        { id: 'ai', label: 'Configuration IA', icon: Cpu },
        { id: 'scraper', label: 'Scraper', icon: SettingsIcon },
        { id: 'sites', label: 'Sites', icon: Globe },
        { id: 'jobs', label: 'Jobs', icon: Clock },
        { id: 'notifications', label: 'Notifications', icon: Bell },
    ];

    return (
        <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-10">
            <div>
                <h2 className="text-2xl font-bold tracking-tight">Administration</h2>
                <p className="text-muted-foreground">Gérez les utilisateurs et la configuration de l'application.</p>
            </div>

            {/* Tabs */}
            <div className="flex flex-wrap gap-2 border-b pb-4">
                {tabs.map(tab => {
                    const Icon = tab.icon;
                    return (
                        <Button
                            key={tab.id}
                            variant={activeTab === tab.id ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setActiveTab(tab.id)}
                        >
                            <Icon className="h-4 w-4 mr-2" />
                            {tab.label}
                        </Button>
                    );
                })}
            </div>

            {/* Users Tab */}
            {activeTab === 'users' && (
                <div className="space-y-6">
                    {/* Change My Password */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2"><Key className="h-5 w-5" />Changer mon mot de passe</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleChangeMyPassword} className="space-y-4">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="space-y-2">
                                        <Label>Mot de passe actuel</Label>
                                        <Input
                                            type="password"
                                            value={passwordChange.currentPassword}
                                            onChange={(e) => setPasswordChange({ ...passwordChange, currentPassword: e.target.value })}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Nouveau mot de passe</Label>
                                        <Input
                                            type="password"
                                            value={passwordChange.newPassword}
                                            onChange={(e) => setPasswordChange({ ...passwordChange, newPassword: e.target.value })}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Confirmer</Label>
                                        <Input
                                            type="password"
                                            value={passwordChange.confirmPassword}
                                            onChange={(e) => setPasswordChange({ ...passwordChange, confirmPassword: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <Button type="submit">Changer le mot de passe</Button>
                            </form>
                        </CardContent>
                    </Card>

                    {/* Create User */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2"><UserPlus className="h-5 w-5" />Créer un utilisateur</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleCreateUser} className="space-y-4">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="space-y-2">
                                        <Label>Nom d'utilisateur</Label>
                                        <Input
                                            value={newUser.username}
                                            onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Mot de passe</Label>
                                        <Input
                                            type="password"
                                            value={newUser.password}
                                            onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Rôle</Label>
                                        <div className="flex items-center gap-2 pt-2">
                                            <Switch
                                                checked={newUser.is_admin}
                                                onCheckedChange={(checked) => setNewUser({ ...newUser, is_admin: checked })}
                                            />
                                            <span className="text-sm">{newUser.is_admin ? 'Administrateur' : 'Utilisateur'}</span>
                                        </div>
                                    </div>
                                </div>
                                <Button type="submit"><UserPlus className="h-4 w-4 mr-2" />Créer</Button>
                            </form>
                        </CardContent>
                    </Card>

                    {/* User List */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2"><Users className="h-5 w-5" />Liste des utilisateurs</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                {users.map(u => (
                                    <div key={u.id} className={cn(
                                        "flex items-center justify-between p-4 rounded-lg border",
                                        !u.is_active && "opacity-50"
                                    )}>
                                        <div className="flex items-center gap-4">
                                            <div className={cn(
                                                "w-10 h-10 rounded-full flex items-center justify-center",
                                                u.is_admin ? "bg-primary/20" : "bg-secondary"
                                            )}>
                                                {u.is_admin ? <Shield className="h-5 w-5 text-primary" /> : <Users className="h-5 w-5" />}
                                            </div>
                                            <div>
                                                <p className="font-medium">{u.username}</p>
                                                <p className="text-sm text-muted-foreground">
                                                    {u.is_admin ? 'Administrateur' : 'Utilisateur'} •
                                                    {u.is_active ? ' Actif' : ' Inactif'}
                                                    {u.last_login && ` • Dernière connexion: ${new Date(u.last_login).toLocaleDateString()}`}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {adminPasswordChange.userId === u.id ? (
                                                <form onSubmit={handleAdminChangePassword} className="flex items-center gap-2">
                                                    <Input
                                                        type="password"
                                                        placeholder="Nouveau mot de passe"
                                                        value={adminPasswordChange.newPassword}
                                                        onChange={(e) => setAdminPasswordChange({ ...adminPasswordChange, newPassword: e.target.value })}
                                                        className="w-40"
                                                    />
                                                    <Button type="submit" size="sm">OK</Button>
                                                    <Button type="button" variant="ghost" size="sm" onClick={() => setAdminPasswordChange({ userId: null, newPassword: '' })}>
                                                        Annuler
                                                    </Button>
                                                </form>
                                            ) : (
                                                <>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => setAdminPasswordChange({ userId: u.id, newPassword: '' })}
                                                        title="Changer le mot de passe"
                                                    >
                                                        <Key className="h-4 w-4" />
                                                    </Button>
                                                    {u.id !== user?.id && (
                                                        <>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handleToggleUserActive(u.id)}
                                                                title={u.is_active ? 'Désactiver' : 'Activer'}
                                                            >
                                                                {u.is_active ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="text-destructive"
                                                                onClick={() => handleDeleteUser(u.id)}
                                                                title="Supprimer"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* AI Configuration Tab */}
            {activeTab === 'ai' && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Cpu className="h-5 w-5" />Configuration IA</CardTitle>
                        <CardDescription>Configure le modèle IA utilisé pour l'analyse des pages produits.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Fournisseur</Label>
                                <Select value={config.ai_provider} onValueChange={(val) => updateSetting('ai_provider', val)}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="ollama">Ollama</SelectItem>
                                        <SelectItem value="openai">OpenAI</SelectItem>
                                        <SelectItem value="anthropic">Anthropic</SelectItem>
                                        <SelectItem value="openrouter">OpenRouter</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            {config.ai_provider !== 'openrouter' ? (
                                <div className="space-y-2">
                                    <Label>Modèle</Label>
                                    <Input value={config.ai_model} onChange={(e) => updateSetting('ai_model', e.target.value)} />
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    <Label>Catégorie</Label>
                                    <Select value={openrouterCategory} onValueChange={setOpenrouterCategory}>
                                        <SelectTrigger><SelectValue placeholder="Filtrer par catégorie" /></SelectTrigger>
                                        <SelectContent>
                                            {openrouterCategories.map(cat => (
                                                <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label>Clé API</Label>
                            <Input
                                type="password"
                                value={config.ai_api_key}
                                onChange={(e) => updateSetting('ai_api_key', e.target.value)}
                                placeholder={config.ai_provider === 'openrouter' ? 'sk-or-...' : 'Optionnel pour Ollama'}
                            />
                        </div>

                        {config.ai_provider === 'openrouter' && (
                            <div className="space-y-4 p-4 border rounded-lg bg-muted/30">
                                <div className="flex items-center justify-between">
                                    <Label className="text-base font-medium">Modèles OpenRouter</Label>
                                    <Button variant="outline" size="sm" onClick={fetchOpenRouterModels} disabled={openrouterLoading}>
                                        <RefreshCw className={cn("h-4 w-4 mr-2", openrouterLoading && "animate-spin")} />
                                        Actualiser
                                    </Button>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {openrouterCategories.map(cat => {
                                        const Icon = categoryIcons[cat.id] || Filter;
                                        return (
                                            <Button
                                                key={cat.id}
                                                variant={openrouterCategory === cat.id ? "default" : "outline"}
                                                size="sm"
                                                onClick={() => setOpenrouterCategory(cat.id)}
                                                className="text-xs"
                                            >
                                                <Icon className="h-3 w-3 mr-1" />{cat.name}
                                            </Button>
                                        );
                                    })}
                                </div>
                                <div className="space-y-2">
                                    <Label>Modèle ({openrouterModels.length} disponibles)</Label>
                                    {openrouterLoading ? (
                                        <div className="text-sm text-muted-foreground py-4 text-center">Chargement...</div>
                                    ) : (
                                        <Select value={config.ai_model} onValueChange={(val) => updateSetting('ai_model', val)}>
                                            <SelectTrigger><SelectValue placeholder="Sélectionner" /></SelectTrigger>
                                            <SelectContent className="max-h-[300px]">
                                                {openrouterModels.map(model => (
                                                    <SelectItem key={model.id} value={model.id}>
                                                        <div className="flex flex-col">
                                                            <span className="font-medium">{model.name}</span>
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatPrice(model.pricing?.prompt)} / {formatPrice(model.pricing?.completion)}
                                                            </span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="pt-2">
                            <Button variant="outline" size="sm" className="w-full" onClick={() => setShowAdvancedAI(!showAdvancedAI)}>
                                Paramètres avancés {showAdvancedAI ? <ChevronUp className="h-4 w-4 ml-2" /> : <ChevronDown className="h-4 w-4 ml-2" />}
                            </Button>
                        </div>

                        {showAdvancedAI && (
                            <div className="space-y-6 pt-4">
                                <div className="space-y-2">
                                    <Label>API Base URL</Label>
                                    <Input value={config.ai_api_base} onChange={(e) => updateSetting('ai_api_base', e.target.value)} />
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <div className="flex justify-between"><Label>Temperature</Label><span className="text-xs">{config.ai_temperature}</span></div>
                                            <Slider min={0} max={1} step={0.1} value={config.ai_temperature} onChange={(e) => updateSetting('ai_temperature', parseFloat(e.target.value))} />
                                        </div>
                                        <div className="space-y-2">
                                            <div className="flex justify-between"><Label>Seuil confiance prix</Label><span className="text-xs">{config.confidence_threshold_price}</span></div>
                                            <Slider min={0} max={1} step={0.1} value={config.confidence_threshold_price} onChange={(e) => updateSetting('confidence_threshold_price', parseFloat(e.target.value))} />
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        <div className="space-y-2">
                                            <Label>Max Tokens</Label>
                                            <Input type="number" value={config.ai_max_tokens} onChange={(e) => updateSetting('ai_max_tokens', parseInt(e.target.value))} />
                                        </div>
                                        <div className="flex items-center justify-between pt-2">
                                            <Label>JSON Repair</Label>
                                            <Switch checked={config.enable_json_repair} onCheckedChange={(checked) => updateSetting('enable_json_repair', checked)} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Scraper Tab */}
            {activeTab === 'scraper' && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><SettingsIcon className="h-5 w-5" />Configuration Scraper</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div><Label>Smart Scroll</Label><p className="text-sm text-muted-foreground">Scroll pour charger le contenu lazy.</p></div>
                            <Switch checked={config.smart_scroll_enabled} onCheckedChange={(checked) => updateSetting('smart_scroll_enabled', checked)} />
                        </div>
                        {config.smart_scroll_enabled && (
                            <div className="space-y-2">
                                <Label>Pixels de scroll</Label>
                                <Input type="number" value={config.smart_scroll_pixels} onChange={(e) => updateSetting('smart_scroll_pixels', parseInt(e.target.value))} />
                            </div>
                        )}
                        <div className="flex items-center justify-between">
                            <div><Label>Contexte texte</Label><p className="text-sm text-muted-foreground">Envoyer le texte de la page à l'IA.</p></div>
                            <Switch checked={config.text_context_enabled} onCheckedChange={(checked) => updateSetting('text_context_enabled', checked)} />
                        </div>
                        {config.text_context_enabled && (
                            <div className="space-y-2">
                                <Label>Longueur max du texte</Label>
                                <Input type="number" value={config.text_context_length} onChange={(e) => updateSetting('text_context_length', parseInt(e.target.value))} />
                            </div>
                        )}
                        <div className="space-y-2">
                            <Label>Timeout (ms)</Label>
                            <Input type="number" value={config.scraper_timeout} onChange={(e) => updateSetting('scraper_timeout', parseInt(e.target.value))} />
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Sites Tab */}
            {activeTab === 'sites' && (
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="flex items-center gap-2"><Globe className="h-5 w-5" />Sites de recherche</CardTitle>
                                <CardDescription>Sites e-commerce français pour la recherche.</CardDescription>
                            </div>
                            <Button variant="outline" size="sm" onClick={resetSitesToDefaults} disabled={resettingSites}>
                                <RotateCcw className={cn("h-4 w-4 mr-2", resettingSites && "animate-spin")} />Réinitialiser
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="text-sm text-muted-foreground">
                            {searchSites.filter(s => s.is_active).length} site(s) actif(s) sur {searchSites.length}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {searchSites.map(site => (
                                <div key={site.id} className={cn("rounded-lg border bg-card p-3 space-y-2", !site.is_active && "opacity-50")}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-medium text-sm truncate">{site.name}</h3>
                                            <p className="text-xs text-muted-foreground truncate">{site.domain}</p>
                                        </div>
                                        <Switch checked={site.is_active} onCheckedChange={() => toggleSiteActive(site)} className="ml-2" />
                                    </div>
                                    {site.category && (
                                        <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs bg-secondary">
                                            {site.category}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Jobs Tab */}
            {activeTab === 'jobs' && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5" />Job de rafraîchissement</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label>Intervalle (minutes)</Label>
                            <Input type="number" min="1" value={jobConfig.refresh_interval_minutes} onChange={(e) => setJobConfig({ ...jobConfig, refresh_interval_minutes: e.target.value })} />
                        </div>
                        <div className="text-sm text-muted-foreground space-y-1">
                            <p>Prochain lancement: {jobConfig.next_run ? new Date(jobConfig.next_run).toLocaleString() : 'Non planifié'}</p>
                            <p>Statut: {jobConfig.running ? 'En cours' : 'Inactif'}</p>
                        </div>
                        <Button onClick={updateJobConfig}>Enregistrer</Button>
                    </CardContent>
                </Card>
            )}

            {/* Notifications Tab */}
            {activeTab === 'notifications' && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5" />Profils de notification</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-8">
                        <form onSubmit={handleProfileSubmit} className="space-y-4 border-b pb-8">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-medium">{editingProfileId ? 'Modifier le profil' : 'Nouveau profil'}</h4>
                                {editingProfileId && <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>Annuler</Button>}
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Nom</Label>
                                    <Input required value={newProfile.name} onChange={(e) => setNewProfile({ ...newProfile, name: e.target.value })} />
                                </div>
                                <div className="space-y-2">
                                    <Label>URL Apprise</Label>
                                    <Input required value={newProfile.apprise_url} onChange={(e) => setNewProfile({ ...newProfile, apprise_url: e.target.value })} />
                                </div>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Intervalle (min)</Label>
                                    <Input type="number" min="1" value={newProfile.check_interval_minutes} onChange={(e) => setNewProfile({ ...newProfile, check_interval_minutes: parseInt(e.target.value) })} />
                                </div>
                                <div className="space-y-2">
                                    <Label>Seuil de baisse (%)</Label>
                                    <Input type="number" min="1" max="100" value={newProfile.price_drop_threshold_percent} onChange={(e) => setNewProfile({ ...newProfile, price_drop_threshold_percent: parseFloat(e.target.value) })} />
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-4">
                                <div className="flex items-center space-x-2">
                                    <Switch checked={newProfile.notify_on_price_drop} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_price_drop: checked })} />
                                    <Label>Baisse de prix</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Switch checked={newProfile.notify_on_target_price} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_target_price: checked })} />
                                    <Label>Prix cible</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Switch checked={newProfile.notify_on_stock_change} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_stock_change: checked })} />
                                    <Label>Changement stock</Label>
                                </div>
                            </div>
                            <Button type="submit">{editingProfileId ? 'Mettre à jour' : 'Créer'}</Button>
                        </form>

                        <div className="space-y-4">
                            <h4 className="text-sm font-medium">Profils existants</h4>
                            {profiles.length === 0 ? (
                                <p className="text-sm text-muted-foreground">Aucun profil créé.</p>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {profiles.map(profile => (
                                        <div key={profile.id} className={cn("relative group rounded-xl border bg-card p-6 space-y-4", editingProfileId === profile.id && "ring-2 ring-primary")}>
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <h3 className="font-semibold">{profile.name}</h3>
                                                    <p className="text-sm text-muted-foreground truncate max-w-[200px]">{profile.apprise_url}</p>
                                                </div>
                                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => editProfile(profile)}><Edit2 className="h-4 w-4" /></Button>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => deleteProfile(profile.id)}><Trash2 className="h-4 w-4" /></Button>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div className="flex items-center gap-2"><Clock className="h-4 w-4 text-muted-foreground" /><span>{profile.check_interval_minutes}m</span></div>
                                                <div className="flex items-center gap-2"><TrendingDown className="h-4 w-4 text-muted-foreground" /><span>{profile.price_drop_threshold_percent}%</span></div>
                                            </div>
                                            <div className="flex flex-wrap gap-2 pt-2">
                                                {profile.notify_on_price_drop && <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs bg-secondary"><DollarSign className="mr-1 h-3 w-3" />Baisse</span>}
                                                {profile.notify_on_target_price && <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs bg-secondary"><CheckCircle2 className="mr-1 h-3 w-3" />Cible</span>}
                                                {profile.notify_on_stock_change && <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs bg-secondary"><Package className="mr-1 h-3 w-3" />Stock</span>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
