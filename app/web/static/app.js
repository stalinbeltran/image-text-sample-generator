import { datasetsView, datasetView } from './datasets.js';
import { el } from './params.js';
import { recipeEditorView, recipesView } from './recipes.js';
import { spinner, toast } from './ui.js';

const view = document.getElementById('view');

const ROUTES = [
  [/^#\/recipes\/([\w-]+)$/, recipeEditorView, 'recipes'],
  [/^#\/recipes$/, recipesView, 'recipes'],
  [/^#\/datasets\/([\w-]+)$/, datasetView, 'datasets'],
  [/^#\/datasets$/, datasetsView, 'datasets'],
];

async function route() {
  const hash = location.hash || '#/recipes';

  for (const [pattern, render, nav] of ROUTES) {
    const match = hash.match(pattern);
    if (!match) continue;

    document.querySelectorAll('nav a[data-nav]').forEach((a) =>
      a.classList.toggle('active', a.dataset.nav === nav)
    );

    view.replaceChildren(spinner());
    try {
      await render(view, ...match.slice(1));
    } catch (e) {
      view.replaceChildren(
        el('div', { class: 'panel' }, el('div', { class: 'err' }, e.message))
      );
      toast(e.message, true);
    }
    return;
  }

  location.hash = '#/recipes';
}

window.addEventListener('hashchange', route);
route();
