import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Sun, Clock, Cpu, Settings as SettingsIcon, Bell, Trash2, ChevronDown, ChevronUp, Edit2, CheckCircle2, AlertCircle, TrendingDown, DollarSign, Package, RefreshCw, Filter, Eye, Code, Brain, Sparkles, Globe, RotateCcw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';

const API_URL = '/api';

// Icônes pour les catégories OpenRouter
const categoryIcons = {
    chat: Sparkles,
    vision: Eye,
    code: Code,
    reasoning: Brain,
    free: DollarSign
};

export default function Settings() {
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
        provider: 'custom',
        discord_webhook: '',
        telegram_token: '',
        telegram_chat_id: '',
        check_interval_minutes: 60,
        notify_on_price_drop: true,
        notify_on_target_price: true,
        price_drop_threshold_percent: 10,
        notify_on_stock_change: true
    });

    const [editingProfileId, setEditingProfileId] = useState(null);
    const [showAdvancedAI, setShowAdvancedAI] = useState(false);

    // Search Sites state
    const [searchSites, setSearchSites] = useState([]);
    const [resettingSites, setResettingSites] = useState(false);

    // OpenRouter state
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
        fetchAll();
    }, []);

    // Charger les modèles OpenRouter quand le provider change ou la catégorie
    useEffect(() => {
        if (config.ai_provider === 'openrouter') {
            fetchOpenRouterModels();
        }
    }, [config.ai_provider, openrouterCategory]);

    const fetchOpenRouterModels = async () => {
        setOpenrouterLoading(true);
        try {
            const params = new URLSearchParams();
            if (config.ai_api_key) {
                params.append('api_key', config.ai_api_key);
            }
            if (openrouterCategory && openrouterCategory !== 'all') {
                params.append('category', openrouterCategory);
            }
            const response = await axios.get(`${API_URL}/openrouter/models?${params.toString()}`);
            setOpenrouterModels(response.data.models || []);
        } catch (error) {
            console.error('Erreur chargement modèles OpenRouter:', error);
            toast.error('Erreur lors du chargement des modèles OpenRouter');
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

    const fetchAll = async () => {
        try {
            const [profilesRes, settingsRes, jobRes, sitesRes] = await Promise.all([
                axios.get(`${API_URL}/notification-profiles`),
                axios.get(`${API_URL}/settings`),
                axios.get(`${API_URL}/jobs/config`),
                axios.get(`${API_URL}/search-sites`)
            ]);

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
            toast.error('Failed to fetch settings');
        }
    };

    const updateSetting = async (key, value) => {
        try {
            await axios.post(`${API_URL}/settings`, { key, value: value.toString() });
            setConfig(prev => ({ ...prev, [key]: value }));
            toast.success('Setting updated');
        } catch (error) {
            toast.error('Failed to update setting');
        }
    };

    const updateJobConfig = async () => {
        try {
            await axios.post(`${API_URL}/jobs/config`, {
                key: 'refresh_interval_minutes',
                value: jobConfig.refresh_interval_minutes.toString()
            });
            toast.success('Job configuration updated');
            fetchAll();
        } catch (error) {
            toast.error('Failed to update job config');
        }
    };

    const handleProfileSubmit = async (e) => {
        e.preventDefault();
        try {
            let finalAppriseUrl = newProfile.apprise_url;

            // Construct Apprise URL based on provider
            if (newProfile.provider === 'discord' && newProfile.discord_webhook) {
                // Parse Discord Webhook: https://discord.com/api/webhooks/{id}/{token} -> discord://{id}/{token}
                const match = newProfile.discord_webhook.match(/webhooks\/(\d+)\/(.+)/);
                if (match) {
                    finalAppriseUrl = `discord://${match[1]}/${match[2]}`;
                } else {
                    toast.error('Invalid Discord Webhook URL');
                    return;
                }
            } else if (newProfile.provider === 'telegram' && newProfile.telegram_token && newProfile.telegram_chat_id) {
                // Construct Telegram URL: tgram://{token}/{chat_id}
                finalAppriseUrl = `tgram://${newProfile.telegram_token}/${newProfile.telegram_chat_id}`;
            }

            const profileData = {
                ...newProfile,
                apprise_url: finalAppriseUrl
            };

            if (editingProfileId) {
                await axios.put(`${API_URL}/notification-profiles/${editingProfileId}`, profileData);
                toast.success('Profile updated');
            } else {
                await axios.post(`${API_URL}/notification-profiles`, profileData);
                toast.success('Profile created');
            }

            setNewProfile({
                name: '',
                apprise_url: '',
                discord_webhook: '',
                telegram_token: '',
                telegram_chat_id: '',
                provider: 'custom',
                check_interval_minutes: 60,
                notify_on_price_drop: true,
                notify_on_target_price: true,
                price_drop_threshold_percent: 10,
                notify_on_stock_change: true
            });
            setEditingProfileId(null);
            fetchAll();
        } catch (error) {
            toast.error(editingProfileId ? 'Failed to update profile' : 'Failed to create profile');
        }
    };

    const editProfile = (profile) => {
        let provider = 'custom';
        let discord_webhook = '';
        let telegram_token = '';
        let telegram_chat_id = '';

        // Deconstruct Apprise URL
        if (profile.apprise_url.startsWith('discord://')) {
            provider = 'discord';
            // discord://{id}/{token} -> https://discord.com/api/webhooks/{id}/{token}
            const parts = profile.apprise_url.replace('discord://', '').split('/');
            if (parts.length >= 2) {
                discord_webhook = `https://discord.com/api/webhooks/${parts[0]}/${parts[1]}`;
            }
        } else if (profile.apprise_url.startsWith('tgram://')) {
            provider = 'telegram';
            // tgram://{token}/{chat_id}
            const parts = profile.apprise_url.replace('tgram://', '').split('/');
            if (parts.length >= 2) {
                telegram_token = parts[0];
                telegram_chat_id = parts[1];
            }
        }

        setNewProfile({
            name: profile.name,
            apprise_url: profile.apprise_url,
            provider,
            discord_webhook,
            telegram_token,
            telegram_chat_id,
            check_interval_minutes: profile.check_interval_minutes,
            notify_on_price_drop: profile.notify_on_price_drop,
            notify_on_target_price: profile.notify_on_target_price,
            price_drop_threshold_percent: profile.price_drop_threshold_percent,
            notify_on_stock_change: profile.notify_on_stock_change
        });
        setEditingProfileId(profile.id);
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    };

    const cancelEdit = () => {
        setNewProfile({
            name: '',
            apprise_url: '',
            check_interval_minutes: 60,
            notify_on_price_drop: true,
            notify_on_target_price: true,
            price_drop_threshold_percent: 10,
            notify_on_stock_change: true
        });
        setEditingProfileId(null);
    };

    const deleteProfile = async (id) => {
        if (confirm('Are you sure you want to delete this profile?')) {
            try {
                await axios.delete(`${API_URL}/notification-profiles/${id}`);
                toast.success('Profile deleted');
                if (editingProfileId === id) {
                    cancelEdit();
                }
                fetchAll();
            } catch (error) {
                toast.error('Failed to delete profile');
            }
        }
    };

    // Search Sites functions
    const toggleSiteActive = async (site) => {
        try {
            await axios.put(`${API_URL}/search-sites/${site.id}`, { is_active: !site.is_active });
            fetchAll();
        } catch (error) {
            toast.error('Erreur lors de la mise à jour');
        }
    };

    const resetSitesToDefaults = async () => {
        if (!confirm('Êtes-vous sûr de vouloir réinitialiser tous les sites ? Cette action va remettre les valeurs par défaut.')) {
            return;
        }
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

    return (
        <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-10">
            <div>
                <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
                <p className="text-muted-foreground">Configure application preferences and notifications.</p>
            </div>

            {/* AI Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Cpu className="h-5 w-5" />AI Configuration</CardTitle>
                    <CardDescription>Configure the AI model used for analyzing product pages.</CardDescription>
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
                                <Input value={config.ai_model} onChange={(e) => updateSetting('ai_model', e.target.value)} placeholder="ex: moondream" />
                            </div>
                        ) : (
                            <div className="space-y-2">
                                <Label>Catégorie</Label>
                                <Select value={openrouterCategory} onValueChange={setOpenrouterCategory}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Filtrer par catégorie" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {openrouterCategories.map(cat => (
                                            <SelectItem key={cat.id} value={cat.id}>
                                                <span className="flex items-center gap-2">
                                                    {cat.name}
                                                </span>
                                            </SelectItem>
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
                            placeholder={config.ai_provider === 'openrouter' ? 'sk-or-...' : 'Optionnel pour les modèles locaux'}
                        />
                    </div>

                    {/* OpenRouter Model Selector */}
                    {config.ai_provider === 'openrouter' && (
                        <div className="space-y-4 p-4 border rounded-lg bg-muted/30">
                            <div className="flex items-center justify-between">
                                <Label className="text-base font-medium">Sélection du modèle OpenRouter</Label>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={fetchOpenRouterModels}
                                    disabled={openrouterLoading}
                                >
                                    <RefreshCw className={cn("h-4 w-4 mr-2", openrouterLoading && "animate-spin")} />
                                    Actualiser
                                </Button>
                            </div>

                            {/* Filtres par catégorie - badges cliquables */}
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
                                            <Icon className="h-3 w-3 mr-1" />
                                            {cat.name}
                                        </Button>
                                    );
                                })}
                            </div>

                            {/* Liste des modèles */}
                            <div className="space-y-2">
                                <Label>Modèle ({openrouterModels.length} disponibles)</Label>
                                {openrouterLoading ? (
                                    <div className="text-sm text-muted-foreground py-4 text-center">
                                        Chargement des modèles...
                                    </div>
                                ) : (
                                    <Select
                                        value={config.ai_model}
                                        onValueChange={(val) => updateSetting('ai_model', val)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Sélectionner un modèle" />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-[300px]">
                                            {openrouterModels.map(model => (
                                                <SelectItem key={model.id} value={model.id}>
                                                    <div className="flex flex-col">
                                                        <span className="font-medium">{model.name}</span>
                                                        <span className="text-xs text-muted-foreground">
                                                            Entrée: {formatPrice(model.pricing?.prompt)} | Sortie: {formatPrice(model.pricing?.completion)}
                                                        </span>
                                                    </div>
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )}
                            </div>

                            {/* Afficher les détails du modèle sélectionné */}
                            {config.ai_model && openrouterModels.length > 0 && (
                                <div className="text-sm p-3 bg-background rounded border">
                                    {(() => {
                                        const selectedModel = openrouterModels.find(m => m.id === config.ai_model);
                                        if (!selectedModel) return <span className="text-muted-foreground">Modèle: {config.ai_model}</span>;
                                        return (
                                            <div className="space-y-2">
                                                <div className="font-medium">{selectedModel.name}</div>
                                                <div className="text-muted-foreground text-xs">{selectedModel.description}</div>
                                                <div className="flex flex-wrap gap-2 pt-1">
                                                    <span className="px-2 py-0.5 bg-primary/10 rounded text-xs">
                                                        Contexte: {selectedModel.context_length?.toLocaleString()} tokens
                                                    </span>
                                                    <span className="px-2 py-0.5 bg-green-500/10 text-green-700 dark:text-green-400 rounded text-xs">
                                                        Entrée: {formatPrice(selectedModel.pricing?.prompt)}
                                                    </span>
                                                    <span className="px-2 py-0.5 bg-blue-500/10 text-blue-700 dark:text-blue-400 rounded text-xs">
                                                        Sortie: {formatPrice(selectedModel.pricing?.completion)}
                                                    </span>
                                                    {selectedModel.categories?.map(cat => (
                                                        <span key={cat} className="px-2 py-0.5 bg-secondary rounded text-xs capitalize">
                                                            {cat}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                    )}

                    <div className="pt-2">
                        <Button
                            variant="outline"
                            size="sm"
                            className="w-full flex items-center justify-between"
                            onClick={() => setShowAdvancedAI(!showAdvancedAI)}
                        >
                            <span>Advanced Settings</span>
                            {showAdvancedAI ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                    </div>

                    {showAdvancedAI && (
                        <div className="space-y-6 pt-4 animate-in slide-in-from-top-2 duration-200">
                            <div className="space-y-2">
                                <Label>API Base URL</Label>
                                <Input value={config.ai_api_base} onChange={(e) => updateSetting('ai_api_base', e.target.value)} />
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Temperature</Label>
                                            <span className="text-xs text-muted-foreground">{config.ai_temperature}</span>
                                        </div>
                                        <Slider
                                            min={0}
                                            max={1}
                                            step={0.1}
                                            value={config.ai_temperature}
                                            onChange={(e) => updateSetting('ai_temperature', parseFloat(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Price Confidence Threshold</Label>
                                            <span className="text-xs text-muted-foreground">{config.confidence_threshold_price}</span>
                                        </div>
                                        <Slider
                                            min={0}
                                            max={1}
                                            step={0.1}
                                            value={config.confidence_threshold_price}
                                            onChange={(e) => updateSetting('confidence_threshold_price', parseFloat(e.target.value))}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex justify-between">
                                            <Label>Stock Confidence Threshold</Label>
                                            <span className="text-xs text-muted-foreground">{config.confidence_threshold_stock}</span>
                                        </div>
                                        <Slider
                                            min={0}
                                            max={1}
                                            step={0.1}
                                            value={config.confidence_threshold_stock}
                                            onChange={(e) => updateSetting('confidence_threshold_stock', parseFloat(e.target.value))}
                                        />
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <Label>Max Tokens</Label>
                                        <Input type="number" value={config.ai_max_tokens} onChange={(e) => updateSetting('ai_max_tokens', parseInt(e.target.value))} />
                                    </div>
                                    <div className="flex items-center justify-between pt-2">
                                        <Label htmlFor="json_repair">Enable JSON Repair</Label>
                                        <Switch id="json_repair" checked={config.enable_json_repair} onCheckedChange={(checked) => updateSetting('enable_json_repair', checked)} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Scraper Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><SettingsIcon className="h-5 w-5" />Scraper Configuration</CardTitle>
                    <CardDescription>Configure how the scraper interacts with web pages.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <Label>Smart Scroll</Label>
                            <p className="text-sm text-muted-foreground">Scroll down to trigger lazy loading.</p>
                        </div>
                        <Switch checked={config.smart_scroll_enabled} onCheckedChange={(checked) => updateSetting('smart_scroll_enabled', checked)} />
                    </div>
                    {config.smart_scroll_enabled && (
                        <div className="space-y-2">
                            <Label>Scroll Pixels</Label>
                            <Input type="number" value={config.smart_scroll_pixels} onChange={(e) => updateSetting('smart_scroll_pixels', parseInt(e.target.value))} />
                        </div>
                    )}
                    <div className="flex items-center justify-between">
                        <div>
                            <Label>Text Context</Label>
                            <p className="text-sm text-muted-foreground">Send page text to AI along with screenshot.</p>
                        </div>
                        <Switch checked={config.text_context_enabled} onCheckedChange={(checked) => updateSetting('text_context_enabled', checked)} />
                    </div>
                    {config.text_context_enabled && (
                        <div className="space-y-2">
                            <Label>Max Text Length</Label>
                            <Input type="number" value={config.text_context_length} onChange={(e) => updateSetting('text_context_length', parseInt(e.target.value))} />
                        </div>
                    )}
                    <div className="space-y-2">
                        <Label>Timeout (ms)</Label>
                        <Input type="number" value={config.scraper_timeout} onChange={(e) => updateSetting('scraper_timeout', parseInt(e.target.value))} />
                    </div>
                </CardContent>
            </Card>

            {/* Job Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Clock className="h-5 w-5" />Automated Refresh Job</CardTitle>
                    <CardDescription>Configure the background job that checks for price updates.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label>Refresh Interval (Minutes)</Label>
                        <Input type="number" min="1" value={jobConfig.refresh_interval_minutes} onChange={(e) => setJobConfig({ ...jobConfig, refresh_interval_minutes: e.target.value })} />
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                        <p>Next run: {jobConfig.next_run ? new Date(jobConfig.next_run).toLocaleString() : 'Not scheduled'}</p>
                        <p>Status: {jobConfig.running ? 'Running' : 'Idle'}</p>
                    </div>
                    <Button onClick={updateJobConfig}>Save Job Config</Button>
                </CardContent>
            </Card>

            {/* Search Sites Configuration */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2"><Globe className="h-5 w-5" />Sites de recherche</CardTitle>
                            <CardDescription>Sites e-commerce français configurés pour la recherche de produits.</CardDescription>
                        </div>
                        <Button variant="outline" size="sm" onClick={resetSitesToDefaults} disabled={resettingSites}>
                            <RotateCcw className={cn("h-4 w-4 mr-2", resettingSites && "animate-spin")} />
                            Réinitialiser
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                        <span>{searchSites.filter(s => s.is_active).length} site(s) actif(s) sur {searchSites.length}</span>
                    </div>

                    {searchSites.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4 text-center">Aucun site configuré. Cliquez sur "Réinitialiser" pour charger les sites par défaut.</p>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {searchSites.map(site => (
                                <div key={site.id} className={cn(
                                    "relative overflow-hidden rounded-lg border bg-card text-card-foreground shadow-sm transition-all",
                                    !site.is_active && "opacity-50"
                                )}>
                                    <div className="p-3 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1 min-w-0">
                                                <h3 className="font-medium text-sm truncate">{site.name}</h3>
                                                <p className="text-xs text-muted-foreground truncate">{site.domain}</p>
                                            </div>
                                            <Switch
                                                checked={site.is_active}
                                                onCheckedChange={() => toggleSiteActive(site)}
                                                className="ml-2"
                                            />
                                        </div>
                                        <div className="flex flex-wrap gap-1">
                                            {site.category && (
                                                <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs bg-secondary text-secondary-foreground">
                                                    {site.category}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Notification Profiles */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5" />Notification Profiles</CardTitle>
                    <CardDescription>Manage notification settings for different groups of items.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                    <form onSubmit={handleProfileSubmit} className="space-y-4 border-b pb-8">
                        <div className="flex items-center justify-between">
                            <h4 className="text-sm font-medium">{editingProfileId ? 'Edit Profile' : 'Create New Profile'}</h4>
                            {editingProfileId && (
                                <Button type="button" variant="ghost" size="sm" onClick={cancelEdit}>Cancel Edit</Button>
                            )}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Name</Label>
                                <Input required value={newProfile.name} onChange={(e) => setNewProfile({ ...newProfile, name: e.target.value })} placeholder="e.g., Email Alerts" />
                            </div>
                            <div className="space-y-4 md:col-span-2 border p-4 rounded-lg bg-muted/20">
                                <div className="space-y-2">
                                    <Label>Notification Provider</Label>
                                    <Select
                                        value={newProfile.provider || 'custom'}
                                        onValueChange={(val) => {
                                            setNewProfile(prev => ({
                                                ...prev,
                                                provider: val,
                                                // Reset fields when switching provider
                                                discord_webhook: '',
                                                telegram_token: '',
                                                telegram_chat_id: '',
                                                apprise_url: val === 'custom' ? prev.apprise_url : ''
                                            }));
                                        }}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="custom">Custom (Apprise URL)</SelectItem>
                                            <SelectItem value="discord">Discord</SelectItem>
                                            <SelectItem value="telegram">Telegram</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {(!newProfile.provider || newProfile.provider === 'custom') && (
                                    <div className="space-y-2">
                                        <Label>Apprise URL</Label>
                                        <Input
                                            required
                                            value={newProfile.apprise_url}
                                            onChange={(e) => setNewProfile({ ...newProfile, apprise_url: e.target.value })}
                                            placeholder="mailto://user:pass@gmail.com"
                                            className="font-mono text-sm"
                                        />
                                        <p className="text-xs text-muted-foreground">
                                            See <a href="https://github.com/caronc/apprise/wiki" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Apprise documentation</a> for supported services.
                                        </p>
                                    </div>
                                )}

                                {newProfile.provider === 'discord' && (
                                    <div className="space-y-2">
                                        <Label>Discord Webhook URL</Label>
                                        <Input
                                            value={newProfile.discord_webhook}
                                            onChange={(e) => setNewProfile({ ...newProfile, discord_webhook: e.target.value })}
                                            placeholder="https://discord.com/api/webhooks/..."
                                            className="font-mono text-sm"
                                        />
                                        <p className="text-xs text-muted-foreground">
                                            Paste the full Webhook URL from Discord Server Settings &gt; Integrations &gt; Webhooks.
                                        </p>
                                    </div>
                                )}

                                {newProfile.provider === 'telegram' && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Bot Token</Label>
                                            <Input
                                                value={newProfile.telegram_token}
                                                onChange={(e) => setNewProfile({ ...newProfile, telegram_token: e.target.value })}
                                                placeholder="123456789:ABCdef..."
                                                className="font-mono text-sm"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Chat ID</Label>
                                            <Input
                                                value={newProfile.telegram_chat_id}
                                                onChange={(e) => setNewProfile({ ...newProfile, telegram_chat_id: e.target.value })}
                                                placeholder="-100123456789"
                                                className="font-mono text-sm"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Check Interval (Minutes)</Label>
                                <Input type="number" min="1" value={newProfile.check_interval_minutes} onChange={(e) => setNewProfile({ ...newProfile, check_interval_minutes: parseInt(e.target.value) })} />
                            </div>
                            <div className="space-y-2">
                                <Label>Price Drop Threshold (%)</Label>
                                <Input type="number" min="1" max="100" value={newProfile.price_drop_threshold_percent} onChange={(e) => setNewProfile({ ...newProfile, price_drop_threshold_percent: parseFloat(e.target.value) })} />
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-4">
                            <div className="flex items-center space-x-2">
                                <Switch checked={newProfile.notify_on_price_drop} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_price_drop: checked })} />
                                <Label>Notify on Drop</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <Switch checked={newProfile.notify_on_target_price} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_target_price: checked })} />
                                <Label>Notify on Target</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <Switch checked={newProfile.notify_on_stock_change} onCheckedChange={(checked) => setNewProfile({ ...newProfile, notify_on_stock_change: checked })} />
                                <Label>Notify on Stock Change</Label>
                            </div>
                        </div>
                        <Button type="submit">{editingProfileId ? 'Update Profile' : 'Create Profile'}</Button>
                    </form>

                    <div className="space-y-4">
                        <h4 className="text-sm font-medium">Existing Profiles</h4>
                        {profiles.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No profiles created yet.</p>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {profiles.map(profile => (
                                    <div key={profile.id} className={cn(
                                        "relative group overflow-hidden rounded-xl border bg-card text-card-foreground shadow transition-all hover:shadow-md",
                                        editingProfileId === profile.id && "ring-2 ring-primary"
                                    )}>
                                        <div className="p-6 space-y-4">
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <h3 className="font-semibold leading-none tracking-tight">{profile.name}</h3>
                                                    <p className="text-sm text-muted-foreground mt-1 truncate max-w-[200px]" title={profile.apprise_url}>{profile.apprise_url}</p>
                                                </div>
                                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => editProfile(profile)}>
                                                        <Edit2 className="h-4 w-4" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => deleteProfile(profile.id)}>
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <Clock className="h-4 w-4 text-muted-foreground" />
                                                    <span>{profile.check_interval_minutes}m interval</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <TrendingDown className="h-4 w-4 text-muted-foreground" />
                                                    <span>{profile.price_drop_threshold_percent}% drop</span>
                                                </div>
                                            </div>

                                            <div className="flex flex-wrap gap-2 pt-2">
                                                {profile.notify_on_price_drop && (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                                                        <DollarSign className="mr-1 h-3 w-3" /> Price Drop
                                                    </span>
                                                )}
                                                {profile.notify_on_target_price && (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                                                        <CheckCircle2 className="mr-1 h-3 w-3" /> Target Hit
                                                    </span>
                                                )}
                                                {profile.notify_on_stock_change && (
                                                    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
                                                        <Package className="mr-1 h-3 w-3" /> Stock Change
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="absolute top-0 right-0 p-6 opacity-5 pointer-events-none">
                                            <Bell className="h-24 w-24" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

        </div>
    );
}
