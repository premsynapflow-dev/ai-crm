(function() {
  // Wait for DOM
  const initWidget = () => {
    // Prevent multiple initializations
    if (document.getElementById('synapflow-widget-container')) return;

    const config = window.synapflowWidget || {};
    const apiKey = config.apiKey || '';
    const companyName = config.companyName || 'Support';
    
    // Find the script tag that loaded this script to determine origin, or default to railway production
    const scripts = document.getElementsByTagName('script');
    let origin = 'https://synapflow.up.railway.app';
    for (let script of scripts) {
      if (script.src.includes('/widget.js')) {
        const url = new URL(script.src);
        origin = url.origin;
        break;
      }
    }

    const container = document.createElement('div');
    container.id = 'synapflow-widget-container';
    container.style.position = 'fixed';
    container.style.bottom = '20px';
    container.style.right = '20px';
    container.style.zIndex = '999999';
    // Closed Dimensions: 80x80 roughly. Opened: 400x600.
    container.style.width = '80px';
    container.style.height = '80px';
    container.style.transition = 'width 0.3s, height 0.3s';
    
    const iframe = document.createElement('iframe');
    const params = new URLSearchParams({
      apiKey: apiKey,
      companyName: companyName
    });
    
    iframe.src = `${origin}/embed?${params.toString()}`;
    iframe.style.border = 'none';
    iframe.style.width = '100%';
    iframe.style.height = '100%';
    iframe.style.background = 'transparent';
    iframe.allowTransparency = 'true';
    
    container.appendChild(iframe);
    document.body.appendChild(container);

    // Listen for resize messages from iframe
    window.addEventListener('message', (event) => {
      // Validate origin if strict security is needed, but for now accept internal widget messages
      if (event.data && event.data.type === 'SYNAPFLOW_WIDGET_RESIZE') {
        if (event.data.isOpen) {
          container.style.width = '380px';
          container.style.height = '600px';
        } else {
          container.style.width = '80px';
          container.style.height = '80px';
        }
      }
    });
  };

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initWidget();
  } else {
    document.addEventListener('DOMContentLoaded', initWidget);
  }
})();
