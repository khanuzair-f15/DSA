class Solution {
public:
    vector<string> sortPeople(vector<string>& names, vector<int>& heights) {
        // vector of pairs to sort height and names in order at once
        vector<pair<string, int>> v;
        // assingning the value to vector pair
        for (int i = 0; i < names.size(); i++) {
            v.push_back({names[i], heights[i]});
        }

        // the vector is sorted in decreasing order
        sort(v.begin(), v.end(),
             [](auto& a, auto& b) { return a.second > b.second; });

        // creating another vector to assign the values for returning

        vector<string> ans;
        for (auto p : v) {
            ans.push_back(p.first);
        }
        return ans;
    }
};