class Solution {
public:
    int numJewelsInStones(string jewels, string stones) {

        // sabse pehle ek int ans liya, jo final answer return karega
        int ans = 0;

        // ab banaya ek array jisme A-Z aur a-z store karenge
        int arr[52] = {}; // saare elements ko 0 se initialize kiya

        for (char c : stones) {         // stones ke characters ko char by char access kiya

            if (c >= 'A' && c <= 'Z') { // capital letters ko separate kiya

                // A ka ASCII code 65 hota hai
                // assume c = 'A'
                // 'A' - 'A' = 65 - 65 = 0
                // isliye A index 0 par store hoga
                //
                // B -> 66 - 65 = 1
                // C -> 67 - 65 = 2
                // ...
                // Z -> 90 - 65 = 25
                //
                // isliye A-Z index 0-25 par store honge
                arr[c - 'A']++;

            } else if (c >= 'a' && c <= 'z') {

                // same logic lowercase letters ke liye
                // a -> 0
                // b -> 1
                // ...
                // z -> 25
                //
                // +26 isliye kiya kyuki index 0-25 par
                // hum already A-Z store kar chuke hain
                //
                // isliye lowercase a-z index 26-51 par store honge
                arr[c - 'a' + 26]++;
            }
        }

        // ab jewels ke characters ko check karenge
        for (char c : jewels) {

            if (c >= 'A' && c <= 'Z') {

                // agar capital letter hai,
                // uska corresponding index nikal kar
                // stones me uski frequency ans me add karenge
                ans += arr[c - 'A'];

            } else if (c >= 'a' && c <= 'z') {

                // agar lowercase letter hai,
                // uska corresponding index nikal kar
                // stones me uski frequency ans me add karenge
                ans += arr[c - 'a' + 26];
            }
        }

        return ans;
    }
};