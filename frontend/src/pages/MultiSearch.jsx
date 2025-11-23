import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Search as SearchIcon, Loader2, ExternalLink, TrendingUp, Package } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

const API_URL = '/api';

export default function MultiSearch() {
    const { t } = useTranslation();
    const [query, setQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [progress, setProgress] = useState(null);
    const [results, setResults] = useState([]);
    const eventSourceRef = useRef(null);

    const handleSearch = async (e) => {
        e.preventDefault();
        if (!query.trim()) {
            toast.error('Veuillez entrer une recherche');
            return;
        }

        // Fermer l'EventSource précédent si existant
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        setIsSearching(true);
        setResults([]);
        setProgress({ status: 'searching', total: 0, completed: 0 });

        // Construire l'URL - recherche sur TOUS les sites actifs
        const params = new URLSearchParams({
            q: query.trim(),
            max_results: 50, // Plus de résultats pour la comparaison
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

    // Grouper les résultats par produit similaire (basé sur le titre)
    const groupedResults = results.reduce((acc, result) => {
        // Simplifier le titre pour le regroupement
        const simplifiedTitle = result.title.toLowerCase().substring(0, 50);

        if (!acc[simplifiedTitle]) {
            acc[simplifiedTitle] = [];
        }
        acc[simplifiedTitle].push(result);
        return acc;
    }, {});

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Comparateur de Prix</h2>
                    <p className="text-muted-foreground">
                        Recherchez un produit sur tous les sites et comparez les prix
                    </p>
                </div>
            </div>

            {/* Search Form */}
            <Card>
                <CardContent className="pt-6">
                    <form onSubmit={handleSearch} className="space-y-4">
                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <SearchIcon className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                                <Input
                                    type="text"
                                    placeholder="Rechercher un produit sur tous les sites..."
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
                                        Comparer
                                    </>
                                )}
                            </Button>
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
                                <span>{progressPercent}%</span>
                            </div>
                            <Progress value={progressPercent} />
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Results Table */}
            {results.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5" />
                            Résultats de comparaison
                        </CardTitle>
                        <CardDescription>
                            {results.length} produit{results.length > 1 ? 's' : ''} trouvé{results.length > 1 ? 's' : ''} avec prix
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b">
                                        <th className="text-left p-3 font-medium">Site</th>
                                        <th className="text-left p-3 font-medium">Produit</th>
                                        <th className="text-right p-3 font-medium">Prix</th>
                                        <th className="text-center p-3 font-medium">Stock</th>
                                        <th className="text-right p-3 font-medium">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {results.map((result, index) => (
                                        <tr key={index} className="border-b hover:bg-muted/50 transition-colors">
                                            <td className="p-3">
                                                <div className="flex flex-col">
                                                    <span className="font-medium">{result.site_name}</span>
                                                    <span className="text-xs text-muted-foreground">{result.site_domain}</span>
                                                </div>
                                            </td>
                                            <td className="p-3">
                                                <div className="max-w-md">
                                                    <p className="font-medium line-clamp-2">{result.title}</p>
                                                </div>
                                            </td>
                                            <td className="p-3 text-right">
                                                {result.price !== null ? (
                                                    <span className="text-lg font-bold text-primary">
                                                        {result.price.toFixed(2)} {result.currency || 'EUR'}
                                                    </span>
                                                ) : (
                                                    <span className="text-sm text-muted-foreground">Prix non disponible</span>
                                                )}
                                            </td>
                                            <td className="p-3 text-center">
                                                {result.in_stock === true && (
                                                    <Badge variant="success" className="bg-green-500/10 text-green-700 dark:text-green-400">
                                                        <Package className="h-3 w-3 mr-1" />
                                                        En stock
                                                    </Badge>
                                                )}
                                                {result.in_stock === false && (
                                                    <Badge variant="destructive">Rupture</Badge>
                                                )}
                                                {result.in_stock === null && (
                                                    <span className="text-xs text-muted-foreground">-</span>
                                                )}
                                            </td>
                                            <td className="p-3">
                                                <div className="flex items-center justify-end gap-2">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => window.open(result.url, '_blank')}
                                                    >
                                                        <ExternalLink className="h-3 w-3 mr-1" />
                                                        Voir
                                                    </Button>
                                                    <Button
                                                        variant="default"
                                                        size="sm"
                                                        onClick={() => handleAddToMonitoring(result)}
                                                    >
                                                        Suivre
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Empty State */}
            {!isSearching && results.length === 0 && progress?.status === 'completed' && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <SearchIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                        <h3 className="text-lg font-medium mb-2">Aucun produit trouvé</h3>
                        <p className="text-muted-foreground">
                            Essayez avec d'autres termes de recherche
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
