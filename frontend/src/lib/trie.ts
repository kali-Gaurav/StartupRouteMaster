/**
 * Prefix Trie for Fast Autocomplete (Suggestion #24)
 * $O(K)$ lookup complexity where K is word length.
 */

class TrieNode {
  children: Record<string, TrieNode> = {};
  isEndOfWord: boolean = false;
  data: any = null; // Store station object
}

export class StationTrie {
  root: TrieNode = new TrieNode();

  insert(word: string, stationData: any) {
    let node = this.root;
    const cleanWord = word.toLowerCase().trim();
    for (const char of cleanWord) {
      if (!node.children[char]) {
        node.children[char] = new TrieNode();
      }
      node = node.children[char];
    }
    node.isEndOfWord = true;
    node.data = stationData;
  }

  search(prefix: string, limit: number = 10): any[] {
    let node = this.root;
    const results: any[] = [];
    const cleanPrefix = prefix.toLowerCase().trim();

    for (const char of cleanPrefix) {
      if (!node.children[char]) return [];
      node = node.children[char];
    }

    this._collectAll(node, results, limit);
    return results;
  }

  private _collectAll(node: TrieNode, results: any[], limit: number) {
    if (results.length >= limit) return;
    if (node.isEndOfWord) results.push(node.data);

    for (const char in node.children) {
      this._collectAll(node.children[char], results, limit);
    }
  }
}
