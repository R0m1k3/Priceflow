import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Search as SearchIcon, Loader2, Plus, ExternalLink, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Checkbox } from '@/components/ui/checkbox';
import { SearchResultCard } from '@/components/search/SearchResultCard';
import { Link } from 'react-router-dom';

const API_URL = '/api';

export default function Search() {
    const { t } = useTranslation();
    const [query, setQuery] = useState('');
    const [sites, setSites] = useState([]);
    const [selectedSites, setSelectedSites] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [progress, setProgress] = useState(null);
    const [results, setResults] = useState([]);
    const eventSourceRef = useRef(null);

    // Charger les sites au démarrage
    useEffect(() => {
        loadSites();
    }, []);

    const loadSites = async () => {
        try {
            const response = await axios.get(`${API_URL}/search-sites`);
            setSites(response.data);
            // Sélectionner tous les sites actifs par défaut
            setSelectedSites(
                response.data
                    .filter(site => site.is_active)
                    .map(site => site.id)
            );
        } catch (error) {
            console.error('Error loading sites:', error);
            toast.error('Erreur lors du chargement des sites');
        }
    };

    const toggleSite = (siteId) => {
        setSelectedSites(prev =>
            prev.includes(siteId)
                ? prev.filter(id => id !== siteId)
                : [...prev, siteId]
        );
    };

    const handleSearch = async (e) => {
        e.preventDefault();
        if (!query.trim() || selectedSites.length === 0) {
            toast.error('Veuillez entrer une recherche et sélectionner au moins un site');
            return;
        }

        // Fermer l'EventSource précédent si existant
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        setIsSearching(true);
        setResults([]);
        setProgress({ status: 'searching', total: 0, completed: 0 });

        // Construire l'URL avec les paramètres
        const params = new URLSearchParams({
            q: query.trim(),
            sites: selectedSites.join(','),
            max_results: 20,
        });

        // Créer l'EventSource pour SSE
        const eventSource = new EventSource(`${API_URL}/search?${params}`);
        eventSourceRef.current = eventSource;

        eventSource.addEventListener('progress', (event) => {
            try {
                const data = JSON.parse(event.data);
                setProgress(data);
                setResults(data.results || []);

                if (data.status === 'completed' || data.status === 'error') {
                    setIsSearching(false);
                    eventSource.close();

                    if (data.status === 'completed') {
                        toast.success(`${data.results?.length || 0} produits trouvés`);
                    } else if (data.message) {
                        toast.error(data.message);
                    }
                }
            } catch (error) {
                console.error('Error parsing SSE data:', error);
            }
        });

        eventSource.onerror = () => {
            setIsSearching(false);
            eventSource.close();
            toast.error('Erreur de connexion au serveur');
        };
    };

    const handleAddToMonitoring = async (result) => {
        try {
            await axios.post(`${API_URL}/items`, {
                url: result.url,
                name: result.title,
                target_price: null,
                check_interval_minutes: 60,
            });
            toast.success(`"${result.title}" ajouté au monitoring`);
        } catch (error) {
            console.error('Error adding item:', error);
            toast.error("Erreur lors de l'ajout au monitoring");
        }
    };

    const progressPercent = progress
        ? Math.round((progress.completed / Math.max(progress.total, 1)) * 100)
        : 0;

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Recherche de produits</h2>
                    <p className="text-muted-foreground">
                        Recherchez des produits sur plusieurs sites et ajoutez-les au monitoring
                    </p>
                </div>
                <Link to="/settings">
                    <Button variant="outline" size="sm">
                        <Settings className="h-4 w-4 mr-2" />
                        Gérer les sites
                    </Button>
                </Link>
            </div>

            {/* Search Form */}
            <Card>
                <CardContent className="pt-6">
                    <form onSubmit={handleSearch} className="space-y-4">
                        {/* Search Input */}
                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <SearchIcon className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                                <Input
                                    type="text"
                                    placeholder="Rechercher un produit..."
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    className="pl-9"
                                    disabled={isSearching}
                                />
                            </div>
                            <Button type="submit" disabled={isSearching || !query.trim()}>
                                {isSearching ? (
                                    <>
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        Recherche...
                                    </>
                                ) : (
                                    <>
                                        <SearchIcon className="h-4 w-4 mr-2" />
                                        Rechercher
                                    </>
                                )}
                            </Button>
                        </div>

                        {/* Site Selection */}
                        <div className="space-y-2">
                            <p className="text-sm font-medium">Sites de recherche :</p>
                            <div className="flex flex-wrap gap-3">
                                {sites.filter(s => s.is_active).map(site => (
                                    <label
                                        key={site.id}
                                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                                            selectedSites.includes(site.id)
                                                ? 'bg-primary/10 border-primary'
                                                : 'bg-background border-border hover:bg-muted'
                                        }`}
                                    >
                                        <Checkbox
                                            checked={selectedSites.includes(site.id)}
                                            onCheckedChange={() => toggleSite(site.id)}
                                        />
                                        <span className="text-sm">{site.name}</span>
                                    </label>
                                ))}
                                {sites.filter(s => s.is_active).length === 0 && (
                                    <p className="text-sm text-muted-foreground">
                                        Aucun site configuré.{' '}
                                        <Link to="/settings" className="text-primary underline">
                                            Ajouter des sites
                                        </Link>
                                    </p>
                                )}
                            </div>
                        </div>
                    </form>
                </CardContent>
            </Card>

            {/* Progress Bar */}
            {progress && isSearching && (
                <Card>
                    <CardContent className="pt-6">
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                                <span>{progress.message || 'Recherche en cours...'}</span>
                                <span>{progress.completed}/{progress.total}</span>
                            </div>
                            <Progress value={progressPercent} />
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Results */}
            {results.length > 0 && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">
                            {results.length} produit{results.length > 1 ? 's' : ''} trouvé{results.length > 1 ? 's' : ''}
                        </h3>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                        {results.map((result, index) => (
                            <SearchResultCard
                                key={`${result.url}-${index}`}
                                result={result}
                                onAddToMonitoring={() => handleAddToMonitoring(result)}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!isSearching && results.length === 0 && progress?.status === 'completed' && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <SearchIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                        <h3 className="text-lg font-medium mb-2">Aucun produit trouvé</h3>
                        <p className="text-muted-foreground">
                            Essayez avec d'autres termes de recherche ou sélectionnez plus de sites
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
