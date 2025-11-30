import React, { useState, useRef } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Search as SearchIcon, Loader2, Star, ShoppingCart, ExternalLink, Tag } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

const API_URL = '/api';

export default function AmazonSearch() {
    const { t } = useTranslation();
    const [query, setQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [progress, setProgress] = useState(null);
    const [results, setResults] = useState([]);
    const eventSourceRef = useRef(null);

    const handleSearch = async (e) => {
        e.preventDefault();
        if (!query.trim()) {
            toast.error('Veuillez entrer un terme de recherche');
            return;
        }

        // Fermer l'EventSource précédent si existant
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        setIsSearching(true);
        setResults([]);
        setProgress({ status: 'searching', total: 1, completed: 0 });

        // Construire l'URL avec les paramètres
        const params = new URLSearchParams({
            q: query.trim(),
            max_results: 20,
        });

        // Créer l'EventSource pour SSE
        const eventSource = new EventSource(`${API_URL}/amazon/search?${params}`);
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
                        toast.success(data.message);
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

    const progressPercent = progress
        ? Math.round((progress.completed / Math.max(progress.total, 1)) * 100)
        : 0;

    const formatPrice = (price, originalPrice) => {
        if (!price) return 'Prix indisponible';

        const formattedPrice = price.toFixed(2);
        if (originalPrice && originalPrice > price) {
            const discount = Math.round(((originalPrice - price) / originalPrice) * 100);
            return (
                <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-green-600">{formattedPrice}€</span>
                    <span className="text-sm text-muted-foreground line-through">{originalPrice.toFixed(2)}€</span>
                    <Badge variant="destructive" className="text-xs">-{discount}%</Badge>
                </div>
            );
        }
        return <span className="text-2xl font-bold">{formattedPrice}€</span>;
    };

    const renderRating = (rating, reviewsCount) => {
        if (!rating) return null;

        return (
            <div className="flex items-center gap-1">
                <div className="flex">
                    {[...Array(5)].map((_, i) => (
                        <Star
                            key={i}
                            className={`h-4 w-4 ${i < Math.floor(rating)
                                    ? 'fill-yellow-400 text-yellow-400'
                                    : 'text-gray-300'
                                }`}
                        />
                    ))}
                </div>
                <span className="text-sm font-medium">{rating.toFixed(1)}</span>
                {reviewsCount && (
                    <span className="text-sm text-muted-foreground">
                        ({reviewsCount.toLocaleString('fr-FR')})
                    </span>
                )}
            </div>
        );
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="text-2xl font-bold tracking-tight">Amazon France</h2>
                        <Badge variant="outline" className="bg-orange-50 border-orange-200">
                            🇫🇷 France
                        </Badge>
                    </div>
                    <p className="text-muted-foreground mt-1">
                        Recherchez parmi des millions de produits sur Amazon.fr
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
                                    placeholder="Rechercher un produit sur Amazon..."
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

                        {/* Info */}
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <div className="flex items-center gap-1">
                                <div className="h-2 w-2 rounded-full bg-green-500"></div>
                                <span>Anti-détection activé</span>
                            </div>
                            <span>•</span>
                            <span>Max 20 résultats</span>
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

            {/* Results */}
            {results.length > 0 && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">
                            {results.length} produit{results.length > 1 ? 's' : ''} trouvé{results.length > 1 ? 's' : ''}
                        </h3>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                        {results.map((product, index) => (
                            <Card key={index} className="overflow-hidden hover:shadow-lg transition-shadow">
                                <CardContent className="p-0">
                                    {/* Image */}
                                    {product.image_url && (
                                        <div className="relative aspect-square bg-gray-50 flex items-center justify-center p-4">
                                            <img
                                                src={product.image_url}
                                                alt={product.title}
                                                className="max-h-full max-w-full object-contain"
                                            />
                                            {product.sponsored && (
                                                <Badge
                                                    variant="secondary"
                                                    className="absolute top-2 left-2 text-xs"
                                                >
                                                    Sponsorisé
                                                </Badge>
                                            )}
                                            {!product.in_stock && (
                                                <Badge
                                                    variant="destructive"
                                                    className="absolute top-2 right-2 text-xs"
                                                >
                                                    Indisponible
                                                </Badge>
                                            )}
                                        </div>
                                    )}

                                    <div className="p-4 space-y-3">
                                        {/* Title */}
                                        <h4 className="font-medium text-sm line-clamp-2 min-h-[2.5rem]">
                                            {product.title}
                                        </h4>

                                        {/* Rating */}
                                        {renderRating(product.rating, product.reviews_count)}

                                        {/* Price */}
                                        <div className="pt-2">
                                            {formatPrice(product.price, product.original_price)}
                                        </div>

                                        {/* Badges */}
                                        <div className="flex flex-wrap gap-1">
                                            {product.prime && (
                                                <Badge variant="default" className="bg-blue-500 text-xs">
                                                    Prime
                                                </Badge>
                                            )}
                                            {product.in_stock && (
                                                <Badge variant="outline" className="text-xs text-green-600 border-green-600">
                                                    En stock
                                                </Badge>
                                            )}
                                        </div>

                                        {/* Actions */}
                                        <div className="pt-2 flex gap-2">
                                            <a
                                                href={product.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="flex-1"
                                            >
                                                <Button
                                                    variant="default"
                                                    size="sm"
                                                    className="w-full"
                                                    asChild
                                                >
                                                    <span>
                                                        <ShoppingCart className="h-4 w-4 mr-1" />
                                                        Voir
                                                    </span>
                                                </Button>
                                            </a>
                                            <a
                                                href={product.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                            >
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    asChild
                                                >
                                                    <span>
                                                        <ExternalLink className="h-4 w-4" />
                                                    </span>
                                                </Button>
                                            </a>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!isSearching && results.length === 0 && !progress && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <div className="mx-auto mb-4 h-16 w-16 rounded-full bg-orange-50 flex items-center justify-center">
                            <SearchIcon className="h-8 w-8 text-orange-500" />
                        </div>
                        <h3 className="text-lg font-medium mb-2">Recherchez sur Amazon France</h3>
                        <p className="text-muted-foreground max-w-md mx-auto">
                            Entrez un terme de recherche pour trouver des produits sur Amazon.fr.
                            Notre système anti-détection garantit un accès fiable aux résultats.
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* No Results */}
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
