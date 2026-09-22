class Solution {
public:
    bool checkIfPangram(string sentence) {
        vector<bool> v(26);
        for (char i : sentence) {

            v[int(i) - 97] = true;

        
        }
        for (bool i : v) {
            if (i == 0) {
                return false;
            }
        }
        return true;
    }
};