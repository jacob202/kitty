/**
 * Schematic Viewer JavaScript
 * Interactive component for electronics schematic visualization
 */

class SchematicViewer {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            zoomEnabled: true,
            panEnabled: true,
            showTooltips: true,
            ...options
        };
        this.components = [];
        this.selectedComponent = null;
        this.scale = 1;
        this.panX = 0;
        this.panY = 0;
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            console.error('SchematicViewer: Container not found');
            return;
        }
        
        this.container.classList.add('schematic-viewer');
        this.setupEventListeners();
        console.log('SchematicViewer initialized');
    }
    
    setupEventListeners() {
        // Component click handling
        this.container.addEventListener('click', (e) => {
            const componentEl = e.target.closest('.component-hotspot');
            if (componentEl) {
                const componentId = componentEl.dataset.componentId;
                this.selectComponent(componentId);
            }
        });
        
        // Zoom handling
        if (this.options.zoomEnabled) {
            this.container.addEventListener('wheel', (e) => {
                e.preventDefault();
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                this.zoom(delta);
            });
        }
    }
    
    loadSchematic(data) {
        this.components = data.components || [];
        this.render();
    }
    
    render() {
        // Clear existing hotspots
        const existing = this.container.querySelectorAll('.component-hotspot');
        existing.forEach(el => el.remove());
        
        // Render component hotspots
        this.components.forEach(comp => {
            const hotspot = document.createElement('div');
            hotspot.className = 'component-hotspot';
            hotspot.dataset.componentId = comp.designator;
            hotspot.style.left = `${comp.x}px`;
            hotspot.style.top = `${comp.y}px`;
            hotspot.title = `${comp.designator}: ${comp.type} ${comp.value || ''}`;
            
            if (this.options.showTooltips) {
                hotspot.addEventListener('mouseenter', () => this.showTooltip(comp));
                hotspot.addEventListener('mouseleave', () => this.hideTooltip());
            }
            
            this.container.appendChild(hotspot);
        });
    }
    
    selectComponent(componentId) {
        // Deselect previous
        if (this.selectedComponent) {
            const prev = this.container.querySelector(`[data-component-id="${this.selectedComponent}"]`);
            if (prev) prev.classList.remove('selected');
        }
        
        // Select new
        this.selectedComponent = componentId;
        const el = this.container.querySelector(`[data-component-id="${componentId}"]`);
        if (el) {
            el.classList.add('selected');
            this.showComponentDetails(componentId);
        }
        
        // Emit event
        this.emit('componentSelected', { componentId });
    }
    
    showComponentDetails(componentId) {
        const comp = this.components.find(c => c.designator === componentId);
        if (!comp) return;
        
        const detailsPanel = document.getElementById('component-details');
        if (detailsPanel) {
            detailsPanel.innerHTML = `
                <h3>${comp.designator}</h3>
                <p>Type: ${comp.type}</p>
                <p>Value: ${comp.value || 'N/A'}</p>
                <p>Confidence: ${(comp.confidence * 100).toFixed(1)}%</p>
            `;
        }
    }
    
    showTooltip(component) {
        const tooltip = document.getElementById('schematic-tooltip') || this.createTooltip();
        tooltip.innerHTML = `
            <strong>${component.designator}</strong><br>
            ${component.type} ${component.value || ''}
        `;
        tooltip.style.display = 'block';
    }
    
    hideTooltip() {
        const tooltip = document.getElementById('schematic-tooltip');
        if (tooltip) tooltip.style.display = 'none';
    }
    
    createTooltip() {
        const tooltip = document.createElement('div');
        tooltip.id = 'schematic-tooltip';
        tooltip.className = 'schematic-tooltip';
        document.body.appendChild(tooltip);
        return tooltip;
    }
    
    zoom(factor) {
        this.scale *= factor;
        this.scale = Math.max(0.1, Math.min(5, this.scale));
        this.applyTransform();
    }
    
    applyTransform() {
        const content = this.container.querySelector('.schematic-content');
        if (content) {
            content.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
        }
    }
    
    emit(eventName, data) {
        const event = new CustomEvent(`schematic:${eventName}`, { detail: data });
        this.container.dispatchEvent(event);
    }
    
    searchComponents(query) {
        const matches = this.components.filter(c => 
            c.designator.toLowerCase().includes(query.toLowerCase()) ||
            c.type.toLowerCase().includes(query.toLowerCase()) ||
            (c.value && c.value.toLowerCase().includes(query.toLowerCase()))
        );
        
        // Highlight matches
        this.container.querySelectorAll('.component-hotspot').forEach(el => {
            el.classList.remove('highlighted');
        });
        
        matches.forEach(comp => {
            const el = this.container.querySelector(`[data-component-id="${comp.designator}"]`);
            if (el) el.classList.add('highlighted');
        });
        
        return matches;
    }
    
    reset() {
        this.scale = 1;
        this.panX = 0;
        this.panY = 0;
        this.selectedComponent = null;
        this.applyTransform();
        this.render();
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SchematicViewer;
}
