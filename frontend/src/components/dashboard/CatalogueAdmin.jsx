import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Play, Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

const API_BASE = '/api/catalogues/admin';

export default function CatalogueAdmin() {
    const [loading, setLoading] = useState(false);
    const [scraping, setScraping] = useState(false);
    const [logs, setLogs] = useState([]);
    const [stats, setStats] = useState(null);
    const [enseignes, setEnseignes] = useState([]);

    useEffect(() => {
        loadEnseignes();
        loadStats();
        loadLogs();
    }, []);

    const loadEnseignes = async () => {
        try {
            const response = await axios.get('/api/catalogues/enseignes');
            setEnseignes(response.data);
        } catch (error) {
            console.error('Error loading enseignes:', error);
        }
    };

    const loadStats = async () => {
        try {
            const response = await axios.get(`${API_BASE}/stats`);
            setStats(response.data);
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    };

    const loadLogs = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE}/scraping/logs?limit=20`);
            setLogs(response.data);
        } catch (error) {
            console.error('Error loading logs:', error);
            toast.error('Erreur lors du chargement des logs');
        } finally {
            setLoading(false);
        }
    };

    const triggerScraping = async (enseigneId = null) => {
        setScraping(true);
        try {
            const params = enseigneId ? { enseigne_id: enseigneId } : {};
            const response = await axios.post(`${API_BASE}/scraping/trigger`, null, { params });

            toast.success(response.data.message);
            toast.info(`${response.data.catalogues_nouveaux} nouveaux catalogues trouvés`);

            // Reload data
            await Promise.all([loadStats(), loadLogs()]);
        } catch (error) {
            console.error('Error triggering scraping:', error);
            toast.error('Erreur lors du déclenchement du scraping');
        } finally {
            setScraping(false);
        }
    };

    const getStatusIcon = (status) => {
        switch (status) {
            case 'success':
                return <CheckCircle2 className="h-5 w-5 text-green-500" />;
            case 'error':
                return <XCircle className="h-5 w-5 text-red-500" />;
            case 'partial':
                return <AlertCircle className="h-5 w-5 text-yellow-500" />;
            default:
                return <Clock className="h-5 w-5 text-gray-500" />;
        }
    };

    const formatDate = (dateString) => {
        const date = new Date(dateString);
        return date.toLocaleString('fr-FR');
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold mb-2">Administration Catalogues</h2>
                <p className="text-muted-foreground">Gérer le scraping des catalogues Bonial</p>
            </div>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-card rounded-lg border p-6">
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">Total Catalogues</h3>
                        <p className="text-3xl font-bold">{stats.total_catalogues}</p>
                    </div>
                    <div className="bg-card rounded-lg border p-6">
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">Dernière Mise à Jour</h3>
                        <p className="text-lg font-medium">
                            {stats.derniere_mise_a_jour
                                ? formatDate(stats.derniere_mise_a_jour)
                                : 'Jamais'}
                        </p>
                    </div>
                    <div className="bg-card rounded-lg border p-6">
                        <h3 className="text-sm font-medium text-muted-foreground mb-2">Prochaine Exécution</h3>
                        <p className="text-lg font-medium">{stats.prochaine_execution}</p>
                    </div>
                </div>
            )}

            {/* Manual Scraping */}
            <div className="bg-card rounded-lg border p-6">
                <h3 className="text-lg font-semibold mb-4">Scraping Manuel</h3>
                <div className="space-y-4">
                    <button
                        onClick={() => triggerScraping()}
                        disabled={scraping}
                        className="w-full md:w-auto px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
                    >
                        {scraping ? (
                            <>
                                <Loader2 className="h-5 w-5 animate-spin" />
                                Scraping en cours...
                            </>
                        ) : (
                            <>
                                <Play className="h-5 w-5" />
                                Scraper toutes les enseignes
                            </>
                        )}
                    </button>

                    <div className="border-t pt-4">
                        <p className="text-sm text-muted-foreground mb-3">Ou scraper une enseigne spécifique:</p>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                            {enseignes.map(enseigne => (
                                <button
                                    key={enseigne.id}
                                    onClick={() => triggerScraping(enseigne.id)}
                                    disabled={scraping}
                                    className="px-4 py-2 rounded-lg border hover:bg-secondary disabled:opacity-50 text-left"
                                >
                                    <div className="font-medium">{enseigne.nom}</div>
                                    <div className="text-xs text-muted-foreground">
                                        {enseigne.catalogues_actifs_count} catalogue(s)
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Catalogues par Enseigne */}
            {stats && (
                <div className="bg-card rounded-lg border p-6">
                    <h3 className="text-lg font-semibold mb-4">Catalogues par Enseigne</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {Object.entries(stats.catalogues_par_enseigne).map(([nom, count]) => (
                            <div key={nom} className="flex justify-between items-center p-3 rounded-lg bg-secondary">
                                <span className="font-medium">{nom}</span>
                                <span className="text-lg font-bold text-primary">{count}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Scraping Logs */}
            <div className="bg-card rounded-lg border p-6">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-semibold">Historique des Scraping</h3>
                    <button
                        onClick={loadLogs}
                        disabled={loading}
                        className="px-3 py-1 text-sm rounded-lg border hover:bg-secondary"
                    >
                        Actualiser
                    </button>
                </div>

                {loading ? (
                    <div className="flex justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                    </div>
                ) : logs.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">Aucun log disponible</p>
                ) : (
                    <div className="space-y-2">
                        {logs.map(log => (
                            <div
                                key={log.id}
                                className="flex items-start gap-3 p-4 rounded-lg border hover:bg-secondary/50 transition-colors"
                            >
                                <div className="mt-0.5">
                                    {getStatusIcon(log.statut)}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-medium">{log.enseigne_nom || 'Toutes'}</span>
                                        <span className="text-xs text-muted-foreground">
                                            {formatDate(log.date_execution)}
                                        </span>
                                    </div>
                                    <div className="text-sm text-muted-foreground">
                                        {log.catalogues_trouves} trouvé(s) • {log.catalogues_nouveaux} nouveau(x)
                                        {log.duree_secondes && ` • ${log.duree_secondes.toFixed(1)}s`}
                                    </div>
                                    {log.message_erreur && (
                                        <div className="text-sm text-red-500 mt-1">
                                            {log.message_erreur}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
