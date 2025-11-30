import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Calendar, BookOpen, Search, ChevronRight, Eye, Trash2, ChevronLeft, X } from 'lucide-react';
import axios from 'axios';
import { useAuth } from '../hooks/use-auth';

const API_BASE = '/api/catalogues';

export default function Catalogues() {
    const [loading, setLoading] = useState(true);
    const [enseignes, setEnseignes] = useState([]);
    const [catalogues, setCatalogues] = useState([]);
    const [selectedEnseigne, setSelectedEnseigne] = useState(null);
    const [pagination, setPagination] = useState({ page: 1, limit: 12, total: 0 });
    const [selectedCatalogue, setSelectedCatalogue] = useState(null);
    const [cataloguePages, setCataloguePages] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [currentPageIndex, setCurrentPageIndex] = useState(0);
    const { user, getAuthHeaders } = useAuth();

    useEffect(() => {
        loadEnseignes();
        loadCatalogues();
    }, []);

    useEffect(() => {
        loadCatalogues();
    }, [pagination.page, selectedEnseigne, searchQuery]);

    const loadEnseignes = async () => {
        try {
            const response = await axios.get(`${API_BASE}/enseignes`);
            if (Array.isArray(response.data)) {
                setEnseignes(response.data);
            } else {
                console.error('API response for enseignes is not an array:', response.data);
                setEnseignes([]);
            }
        } catch (error) {
            console.error('Error loading enseignes:', error);
            toast.error('Erreur lors du chargement des enseignes');
        }
    };

    const loadCatalogues = async () => {
        setLoading(true);
        try {
            const params = {
                page: pagination.page,
                limit: pagination.limit,
                statut: 'actif',
            };

            if (selectedEnseigne) {
                params.enseigne_ids = selectedEnseigne.id.toString();
            }

            if (searchQuery) {
                params.recherche = searchQuery;
            }

            const response = await axios.get(API_BASE, { params });
            if (response.data && Array.isArray(response.data.data)) {
                setCatalogues(response.data.data);
                setPagination(prev => ({ ...prev, total: response.data.pagination.total }));
            } else {
                console.error('API response for catalogues is invalid:', response.data);
                setCatalogues([]);
            }
        } catch (error) {
            console.error('Error loading catalogues:', error);
            toast.error('Erreur lors du chargement des catalogues');
        } finally {
            setLoading(false);
        }
    };

    const loadCataloguePages = async (catalogueId) => {
        try {
            const response = await axios.get(`${API_BASE}/${catalogueId}/pages`);
            setCataloguePages(response.data);
        } catch (error) {
            console.error('Error loading pages:', error);
            toast.error('Erreur lors du chargement des pages');
        }
    };

    const openCatalogue = (catalogue) => {
        setSelectedCatalogue(catalogue);
        setCurrentPageIndex(0); // Reset to first page
        loadCataloguePages(catalogue.id);
    };

    const closeCatalogue = () => {
        setSelectedCatalogue(null);
        setCataloguePages([]);
        setCurrentPageIndex(0);
    };

    const formatDate = (dateString) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
    };

    const isValidNow = (catalogue) => {
        const now = new Date();
        const debut = new Date(catalogue.date_debut);
        const fin = new Date(catalogue.date_fin);
        return now >= debut && now <= fin;
    };

    const deleteCatalogue = async (catalogueId, event) => {
        event.stopPropagation(); // Prevent opening the catalogue

        if (!confirm('Êtes-vous sûr de vouloir supprimer ce catalogue ?')) {
            return;
        }

        try {
            await axios.delete(`${API_BASE}/admin/${catalogueId}`, {
                headers: getAuthHeaders()
            });

            toast.success('Catalogue supprimé');
            loadCatalogues(); // Reload the list
        } catch (error) {
            console.error('Error deleting catalogue:', error);
            toast.error('Erreur lors de la suppression');
        }
    };

    // Keyboard navigation support
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (!selectedCatalogue) return;

            if (e.key === 'ArrowLeft') {
                setCurrentPageIndex(prev => Math.max(0, prev - 1));
            } else if (e.key === 'ArrowRight') {
                setCurrentPageIndex(prev => Math.min(cataloguePages.length - 1, prev + 1));
            } else if (e.key === 'Escape') {
                closeCatalogue();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedCatalogue, cataloguePages.length]);

    return (
        <div className="p-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">Catalogues Promotionnels</h1>
                <p className="text-muted-foreground">
                    Consultez les catalogues et prospectus des enseignes discount
                </p>
            </div>

            {/* Search Bar */}
            <div className="mb-6">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Rechercher dans les catalogues..."
                        className="w-full pl-10 pr-4 py-3 rounded-lg border bg-background"
                        value={searchQuery}
                        onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setPagination(prev => ({ ...prev, page: 1 }));
                        }}
                    />
                </div>
            </div>

            {/* Enseignes Filter */}
            <div className="mb-6">
                <div className="flex gap-2 overflow-x-auto pb-2">
                    <button
                        onClick={() => {
                            setSelectedEnseigne(null);
                            setPagination(prev => ({ ...prev, page: 1 }));
                        }}
                        className={`px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${!selectedEnseigne
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-secondary hover:bg-secondary/80'
                            }`}
                    >
                        Toutes les enseignes
                    </button>
                    {enseignes.map(enseigne => (
                        <button
                            key={enseigne.id}
                            onClick={() => {
                                setSelectedEnseigne(enseigne);
                                setPagination(prev => ({ ...prev, page: 1 }));
                            }}
                            className={`px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${selectedEnseigne?.id === enseigne.id
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-secondary hover:bg-secondary/80'
                                }`}
                            style={
                                selectedEnseigne?.id === enseigne.id
                                    ? { backgroundColor: enseigne.couleur, color: 'white' }
                                    : {}
                            }
                        >
                            {enseigne.nom}
                            {enseigne.catalogues_actifs_count > 0 && (
                                <span className="ml-2 px-2 py-0.5 rounded-full bg-white/20 text-xs">
                                    {enseigne.catalogues_actifs_count}
                                </span>
                            )}
                        </button>
                    ))}
                </div>
            </div>

            {/* Catalogues Grid */}
            {loading ? (
                <div className="flex justify-center items-center py-20">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
            ) : catalogues.length === 0 ? (
                <div className="text-center py-20">
                    <BookOpen className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                    <h3 className="text-lg font-medium mb-2">Aucun catalogue trouvé</h3>
                    <p className="text-muted-foreground">
                        {searchQuery
                            ? 'Aucun catalogue ne correspond à votre recherche'
                            : 'Aucun catalogue disponible pour le moment'}
                    </p>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                        {catalogues.map(catalogue => (
                            <div
                                key={catalogue.id}
                                className="group bg-card rounded-lg border overflow-hidden hover:shadow-lg transition-all cursor-pointer"
                                onClick={() => openCatalogue(catalogue)}
                            >
                                {/* Cover Image */}
                                <div className="relative aspect-[3/4] overflow-hidden bg-secondary">
                                    <img
                                        src={catalogue.image_couverture_url}
                                        alt={catalogue.titre}
                                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                                    />
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                                        <div className="absolute bottom-4 left-4 right-4 text-white">
                                            <Eye className="h-5 w-5 mx-auto mb-2" />
                                            <p className="text-sm text-center">Voir le catalogue</p>
                                        </div>
                                    </div>
                                    {isValidNow(catalogue) && (
                                        <div className="absolute top-2 right-2">
                                            <span className="px-2 py-1 rounded-full bg-green-500 text-white text-xs font-medium">
                                                En cours
                                            </span>
                                        </div>
                                    )}
                                </div>

                                {/* Content */}
                                <div className="p-4">
                                    {/* Enseigne Badge */}
                                    <div
                                        className="inline-block px-3 py-1 rounded-full text-white text-xs font-medium mb-2"
                                        style={{ backgroundColor: catalogue.enseigne.couleur }}
                                    >
                                        {catalogue.enseigne.nom}
                                    </div>

                                    {/* Title */}
                                    <h3 className="font-semibold text-base mb-2 line-clamp-2">
                                        {catalogue.titre}
                                    </h3>

                                    {/* Dates */}
                                    <div className="flex items-center gap-1 text-sm text-muted-foreground mb-2">
                                        <Calendar className="h-4 w-4" />
                                        <span>
                                            {formatDate(catalogue.date_debut)} - {formatDate(catalogue.date_fin)}
                                        </span>
                                    </div>

                                    {/* Pages */}
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                                            <BookOpen className="h-4 w-4" />
                                            <span>{catalogue.nombre_pages} pages</span>
                                        </div>
                                        {user?.is_admin && (
                                            <button
                                                onClick={(e) => deleteCatalogue(catalogue.id, e)}
                                                className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                                title="Supprimer le catalogue"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Pagination */}
                    {pagination.total > pagination.limit && (
                        <div className="mt-8 flex justify-center items-center gap-2">
                            <button
                                onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                                disabled={pagination.page === 1}
                                className="px-4 py-2 rounded-lg border bg-background disabled:opacity-50"
                            >
                                Précédent
                            </button>
                            <span className="px-4 py-2 text-sm text-muted-foreground">
                                Page {pagination.page} sur {Math.ceil(pagination.total / pagination.limit)}
                            </span>
                            <button
                                onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                                disabled={pagination.page >= Math.ceil(pagination.total / pagination.limit)}
                                className="px-4 py-2 rounded-lg border bg-background disabled:opacity-50"
                            >
                                Suivant
                            </button>
                        </div>
                    )}
                </>
            )}

            {/* Catalogue Viewer Modal - Page by Page Navigation */}
            {selectedCatalogue && (
                <div
                    className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center"
                    onClick={closeCatalogue}
                >
                    <div
                        className="relative w-full h-full flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="bg-black/50 backdrop-blur-sm p-4 flex justify-between items-center">
                            <div className="flex items-center gap-4">
                                <h2 className="text-white text-xl font-bold">{selectedCatalogue.titre}</h2>
                                <span className="text-white/70 text-sm">
                                    {selectedCatalogue.enseigne.nom}
                                </span>
                            </div>
                            <div className="flex items-center gap-4">
                                {cataloguePages.length > 0 && (
                                    <span className="text-white text-sm font-medium">
                                        Page {currentPageIndex + 1} / {cataloguePages.length}
                                    </span>
                                )}
                                <button
                                    onClick={closeCatalogue}
                                    className="p-2 text-white hover:bg-white/20 rounded-lg transition-colors"
                                    title="Fermer (ESC)"
                                >
                                    <X className="h-6 w-6" />
                                </button>
                            </div>
                        </div>

                        {/* Main Image Viewer */}
                        <div className="flex-1 flex items-center justify-center relative overflow-hidden">
                            {cataloguePages.length === 0 ? (
                                <Loader2 className="h-12 w-12 animate-spin text-white" />
                            ) : (
                                <>
                                    {/* Current Page Image */}
                                    <div className="w-full h-full flex items-center justify-center p-8">
                                        <img
                                            src={cataloguePages[currentPageIndex]?.image_url}
                                            alt={`Page ${currentPageIndex + 1}`}
                                            className="w-auto h-auto max-w-full max-h-full object-contain rounded-lg shadow-2xl"
                                            style={{ maxHeight: 'calc(100vh - 200px)' }}
                                        />
                                    </div>

                                    {/* Navigation Buttons - Fixed Position */}
                                    {cataloguePages.length > 1 && (
                                        <>
                                            {/* Previous Button */}
                                            <button
                                                onClick={() => setCurrentPageIndex(prev => Math.max(0, prev - 1))}
                                                disabled={currentPageIndex === 0}
                                                className="fixed left-8 top-1/2 -translate-y-1/2 p-4 bg-black/70 hover:bg-black/90 text-white rounded-full disabled:opacity-30 disabled:cursor-not-allowed transition-all z-10"
                                                title="Page précédente (←)"
                                            >
                                                <ChevronLeft className="h-8 w-8" />
                                            </button>

                                            {/* Next Button */}
                                            <button
                                                onClick={() => setCurrentPageIndex(prev => Math.min(cataloguePages.length - 1, prev + 1))}
                                                disabled={currentPageIndex === cataloguePages.length - 1}
                                                className="fixed right-8 top-1/2 -translate-y-1/2 p-4 bg-black/70 hover:bg-black/90 text-white rounded-full disabled:opacity-30 disabled:cursor-not-allowed transition-all z-10"
                                                title="Page suivante (→)"
                                            >
                                                <ChevronRight className="h-8 w-8" />
                                            </button>
                                        </>
                                    )}
                                </>
                            )}
                        </div>

                        {/* Thumbnail Strip */}
                        {cataloguePages.length > 1 && (
                            <div className="bg-black/50 backdrop-blur-sm p-4">
                                <div className="flex gap-2 overflow-x-auto pb-2">
                                    {cataloguePages.map((page, index) => (
                                        <button
                                            key={page.id}
                                            onClick={() => setCurrentPageIndex(index)}
                                            className={`relative flex-shrink-0 w-20 h-28 rounded-lg overflow-hidden border-2 transition-all ${index === currentPageIndex
                                                ? 'border-primary scale-110'
                                                : 'border-white/20 hover:border-white/50'
                                                }`}
                                        >
                                            <img
                                                src={page.image_url}
                                                alt={`Page ${index + 1}`}
                                                className="w-full h-full object-cover"
                                            />
                                            <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white text-xs text-center py-0.5">
                                                {index + 1}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
