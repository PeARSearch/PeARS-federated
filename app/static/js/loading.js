// SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>,
// SPDX-License-Identifier: AGPL-3.0-only

document.getElementById('searchbutton').addEventListener('click', function(e) {
  document.getElementById('searchbutton').classList.add('hidden');
  document.getElementById('loadingbutton').classList.remove('hidden');
});
