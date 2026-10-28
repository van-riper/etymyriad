// The data only changes on a reload, and the ETL workflow purges the
// zone cache right after one. s-maxage keeps browsers out of it, since
// a purge can't reach them and term ids change with every reload.
export const CACHED_UNTIL_RELOAD = 'public, s-maxage=86400';
