// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <map>
#include <string>
#include <vector>

namespace borealis {
struct Io {
    virtual ~Io() = default;
    virtual std::string read(const std::string& path) = 0;
    virtual bool write(const std::string& path, const std::string& value) = 0;
};
struct Change { std::string path, value; };
struct Result {
    bool ok;
    std::string detail, errorPath;
    Result(bool success, const std::string& message, const std::string& path = {})
        : ok(success), detail(message), errorPath(path) {}
};
using Config = std::map<std::string, std::string>;
std::vector<std::string> words(std::string value);
std::string selected(std::string value);
bool allowed(const std::string& path);
class Engine {
public:
    explicit Engine(Io& io) : io_(io) {}
    std::vector<std::string> cpus();
    std::vector<Change> snapshot();
    Result apply(const Config& config, const std::vector<Change>& defaults);
private:
    Io& io_;
    Result commit(const std::vector<Change>& plan);
    bool cap(std::vector<Change>& plan, const std::string& dir,
             const std::string& table, const std::string& min,
             const std::string& max, const std::string& choice, int ceiling);
};
} // namespace borealis
