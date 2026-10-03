// plotly.js-dist-min ships without types; these are the calls the Outputs component makes.
declare module "plotly.js-dist-min" {
  const Plotly: {
    newPlot(el: HTMLElement, data: unknown[], layout?: Record<string, unknown>, config?: Record<string, unknown>): Promise<unknown>;
    purge(el: HTMLElement): void;
  };
  export default Plotly;
}
