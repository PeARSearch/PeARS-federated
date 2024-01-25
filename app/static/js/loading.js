//SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
//SPDX-License-Identifier: AGPL-3.0-only


document.getElementById('searchbutton').addEventListener('click', function(e) {
  document.getElementById("searchbutton").style.display='none';
  document.getElementById("loadingbutton").style.display='block';
  document.getElementById("searchform").submit();
});

document.getElementById('indexurlbutton').addEventListener('click', function(e) {
  document.getElementById("indexurlbutton").style.display='none';
  document.getElementById("loadingurlbutton").style.display='block';
});

document.getElementById('indexfilebutton').addEventListener('click', function(e) {
  document.getElementById("indexfilebutton").style.display='none';
  document.getElementById("loadingfilebutton").style.display='block';
});

document.getElementById('indexbookmarksbutton').addEventListener('click', function(e) {
  document.getElementById("indexbookmarksbutton").style.display='none';
  document.getElementById("loadingbookmarksbutton").style.display='block';
});
