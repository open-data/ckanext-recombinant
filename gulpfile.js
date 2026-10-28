const { src, dest, watch, series } = require('gulp');
const rename = require('gulp-rename');
const sourcemaps = require('gulp-sourcemaps');
const sass = require('gulp-sass')(require('sass'));
const terser = require('gulp-terser');

function compileCustomSass(){
  return src('ckanext/recombinant/assets/source/*.scss')
    // .pipe(sourcemaps.init())
    .pipe(sass({style: 'compressed'}).on('error', sass.logError))
    // .pipe(sourcemaps.write())
    .pipe(rename(function(_fileObj){
      _fileObj.extname = '.min.css';
    }))
    .pipe(dest('ckanext/recombinant/assets/build'));
}


function watchSass(){
  watch('ckanext/recombinant/assets/source/*.scss', compileCustomSass);
}

function minifyCustomJS(){
  return src('ckanext/recombinant/assets/source/*.js', {sourcemaps: false})
    .pipe(terser({'compress': true,
                  'mangle': true}))
    .pipe(rename(function(_fileObj){
      _fileObj.extname = '.min.js';
    }))
    .pipe(dest('ckanext/recombinant/assets/build', {sourcemaps: false}));
}

function watchJS(){
  watch('ckanext/recombinant/assets/source/*.js', minifyCustomJS);
}

exports.build = series(compileCustomSass,
                       minifyCustomJS)
exports.watch = series(watchJS,
                       watchSass);
exports.buildCSS = series(compileCustomSass);
exports.watchCSS = watchSass;
exports.buildJS = series(minifyCustomJS);
exports.watchJS = watchJS;
