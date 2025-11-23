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
    const [channels, setChannels] = useState([]);
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
    const [newChannel, setNewChannel] = useState({
        name: '',
        type: 'email',
        configuration: '',
        // Helper fields for UI
        email_user: '',
        email_pass: '',
        email_host: '',
        email_port: '',
        discord_webhook: '',
        mattermost_webhook: '',
        is_active: true
    });

    const [editingChannelId, setEditingChannelId] = useState(null);
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
            const [channelsRes, settingsRes, jobRes, sitesRes] = await Promise.all([
                axios.get(`${API_URL}/notifications/channels`),
                axios.get(`${API_URL}/settings`),
                axios.get(`${API_URL}/jobs/config`),
                axios.get(`${API_URL}/search-sites`)
            ]);

            setChannels(channelsRes.data);
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

    const handleChannelSubmit = async (e) => {
        e.preventDefault();
        try {
            let configuration = newChannel.configuration;

            // Construct configuration based on type
            if (newChannel.type === 'email') {
                configuration = JSON.stringify({
                    user: newChannel.email_user,
                    password: newChannel.email_pass,
                    host: newChannel.email_host,
                    port: newChannel.email_port
                });
            } else if (newChannel.type === 'discord') {
                configuration = JSON.stringify({
                    webhook_url: newChannel.discord_webhook
                });
            } else if (newChannel.type === 'mattermost') {
                configuration = JSON.stringify({
                    webhook_url: newChannel.mattermost_webhook
                });
            }

            const channelData = {
                name: newChannel.name,
                type: newChannel.type,
                configuration: configuration,
                is_active: newChannel.is_active
            };

            if (editingChannelId) {
                await axios.put(`${API_URL}/notifications/channels/${editingChannelId}`, channelData);
                toast.success('Channel updated');
            } else {
                await axios.post(`${API_URL}/notifications/channels`, channelData);
                toast.success('Channel created');
            }

            resetChannelForm();
            fetchAll();
        } catch (error) {
            toast.error(editingChannelId ? 'Failed to update channel' : 'Failed to create channel');
        }
    };

    const resetChannelForm = () => {
        setNewChannel({
            name: '',
            type: 'email',
            configuration: '',
            email_user: '',
            email_pass: '',
            email_host: '',
            email_port: '',
            discord_webhook: '',
            mattermost_webhook: '',
            is_active: true
        });
        setEditingChannelId(null);
    };

    const editChannel = (channel) => {
        let email_user = '';
        let email_pass = '';
        let email_host = '';
        let email_port = '';
        let discord_webhook = '';
        let mattermost_webhook = '';

        try {
            const config = JSON.parse(channel.configuration);
            if (channel.type === 'email') {
                email_user = config.user || '';
                email_pass = config.password || '';
                email_host = config.host || '';
                email_port = config.port || '';
            } else if (channel.type === 'discord') {
                discord_webhook = config.webhook_url || '';
            } else if (channel.type === 'mattermost') {
                mattermost_webhook = config.webhook_url || '';
            }
        } catch (e) {
            // If config is not JSON, maybe it's a raw URL
        }

        setNewChannel({
            name: channel.name,
            type: channel.type,
            configuration: channel.configuration,
            email_user,
            email_pass,
            email_host,
            email_port,
            discord_webhook,
            mattermost_webhook,
            is_active: channel.is_active
        });
        setEditingChannelId(channel.id);
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    };

    const deleteChannel = async (id) => {
        if (confirm('Are you sure you want to delete this channel?')) {
            try {
                await axios.delete(`${API_URL}/notifications/channels/${id}`);
                toast.success('Channel deleted');
                if (editingChannelId === id) {
                    resetChannelForm();
                }
                fetchAll();
            } catch (error) {
                toast.error('Failed to delete channel');
            }
        }
    };

    const testChannel = async (id) => {
        try {
            await axios.post(`${API_URL}/notifications/channels/${id}/test`);
            toast.success('Test notification queued');
        } catch (error) {
            toast.error('Failed to send test notification');
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
            {/* Notification Channels */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2"><Bell className="h-5 w-5" />Notification Channels</CardTitle>
                    <CardDescription>Configure where you want to receive alerts (Email, Discord, Mattermost).</CardDescription>
                </CardHeader>
                <CardContent className="space-y-8">
                    <form onSubmit={handleChannelSubmit} className="space-y-4 border-b pb-8">
                        <div className="flex items-center justify-between">
                            <h4 className="text-sm font-medium">{editingChannelId ? 'Edit Channel' : 'Create New Channel'}</h4>
                            {editingChannelId && (
                                <Button type="button" variant="ghost" size="sm" onClick={resetChannelForm}>Cancel Edit</Button>
                            )}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Name</Label>
                                <Input required value={newChannel.name} onChange={(e) => setNewChannel({ ...newChannel, name: e.target.value })} placeholder="e.g., My Discord" />
                            </div>
                            <div className="space-y-2">
                                <Label>Type</Label>
                                <Select
                                    value={newChannel.type}
                                    onValueChange={(val) => setNewChannel({ ...newChannel, type: val })}
                                >
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="email">Email</SelectItem>
                                        <SelectItem value="discord">Discord</SelectItem>
                                        <SelectItem value="mattermost">Mattermost</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Configuration Fields based on Type */}
                        <div className="space-y-4 border p-4 rounded-lg bg-muted/20">
                            {newChannel.type === 'email' && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>SMTP User</Label>
                                        <Input value={newChannel.email_user} onChange={(e) => setNewChannel({ ...newChannel, email_user: e.target.value })} placeholder="user@example.com" />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>SMTP Password</Label>
                                        <Input type="password" value={newChannel.email_pass} onChange={(e) => setNewChannel({ ...newChannel, email_pass: e.target.value })} />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>SMTP Host</Label>
                                        <Input value={newChannel.email_host} onChange={(e) => setNewChannel({ ...newChannel, email_host: e.target.value })} placeholder="smtp.gmail.com" />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>SMTP Port</Label>
                                        <Input value={newChannel.email_port} onChange={(e) => setNewChannel({ ...newChannel, email_port: e.target.value })} placeholder="587" />
                                    </div>
                                </div>
                            )}

                            {newChannel.type === 'discord' && (
                                <div className="space-y-2">
                                    <Label>Webhook URL</Label>
                                    <Input value={newChannel.discord_webhook} onChange={(e) => setNewChannel({ ...newChannel, discord_webhook: e.target.value })} placeholder="https://discord.com/api/webhooks/..." />
                                </div>
                            )}

                            {newChannel.type === 'mattermost' && (
                                <div className="space-y-2">
                                    <Label>Webhook URL</Label>
                                    <Input value={newChannel.mattermost_webhook} onChange={(e) => setNewChannel({ ...newChannel, mattermost_webhook: e.target.value })} placeholder="https://mattermost.example.com/hooks/..." />
                                </div>
                            )}
                        </div>

                        <div className="flex items-center space-x-2">
                            <Switch checked={newChannel.is_active} onCheckedChange={(checked) => setNewChannel({ ...newChannel, is_active: checked })} />
                            <Label>Active</Label>
                        </div>

                        <Button type="submit">{editingChannelId ? 'Update Channel' : 'Create Channel'}</Button>
                    </form>

                    <div className="space-y-4">
                        <h4 className="text-sm font-medium">Existing Channels</h4>
                        {channels.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No channels created yet.</p>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {channels.map(channel => (
                                    <div key={channel.id} className={cn(
                                        "relative group overflow-hidden rounded-xl border bg-card text-card-foreground shadow transition-all hover:shadow-md",
                                        editingChannelId === channel.id && "ring-2 ring-primary",
                                        !channel.is_active && "opacity-60"
                                    )}>
                                        <div className="p-6 space-y-4">
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <h3 className="font-semibold leading-none tracking-tight flex items-center gap-2">
                                                        {channel.name}
                                                        {!channel.is_active && <span className="text-xs font-normal text-muted-foreground">(Inactive)</span>}
                                                    </h3>
                                                    <p className="text-sm text-muted-foreground mt-1 capitalize">{channel.type}</p>
                                                </div>
                                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => testChannel(channel.id)} title="Send Test Notification">
                                                        <Bell className="h-4 w-4" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => editChannel(channel)}>
                                                        <Edit2 className="h-4 w-4" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => deleteChannel(channel.id)}>
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>
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
