let
  # nixos-20.03 at 21.07.2020
  nixpkgs = import (builtins.fetchGit {
    url = "https://github.com/nixos/nixpkgs-channels/";
    name = "nixos-20.03-9ea61f7";
    rev = "9ea61f7bc4454734ffbff73c9b6173420fe3147b";
    ref = "refs/heads/nixos-20.03";
  }) { overlays = [NixWithChemistry]; };

  NixWithChemistry =
    let
      repoPath = builtins.fetchGit {
        url = "https://gitlab.com/theoretical-chemistry-jena/nixwithchemistry.git";
        name = "NixWithChemistry";
        rev = "f1b981e437ee1080501391ee9a65d78a351b0df9";
        ref = "refs/heads/master";
      };
    in import "${repoPath}/default.nix";

in nixpkgs
